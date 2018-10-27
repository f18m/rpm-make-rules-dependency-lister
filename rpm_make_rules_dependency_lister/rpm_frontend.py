#!/usr/bin/python3

#
# Purpose: Read an .rpm file and writes an output text file that, if included inside a 
#          Makefile, will instruct GNU make about the dependencies of the .rpm, so that 
#          such RPM can be rebuilt only when one of the dependencies is updated 
#          (rather than unconditionally) thus speeding up the time required by "make".
# Author: fmontorsi
# Creation: May 2018
#

import getopt, sys, os, subprocess, hashlib
import pkg_resources  # part of setuptools

##
## GLOBALS
##

verbose = False

##
## FUNCTIONS
##

def md5_checksum(fname):
    """Computes the MD5 hash of a file on disk
    """
    hash_md5 = hashlib.md5()
    try:
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
    except OSError:
        # this happens when a directory is encountered
        return ""
    except IOError:
        print("Failed opening decompressed file '{}'\n".format(fname))
        sys.exit(3)

    return hash_md5.hexdigest()

def sha256_checksum(filename, block_size=65536):
    """Computes the SHA256 hash of a file on disk
    """
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(block_size), b''):
            sha256.update(block)
    return sha256.hexdigest()

def get_checksum_pairs_from_rpm(rpm_filename):
    """Extracts sha256sums or md5sums from an RPM file and creates
       a list of pairs
           (extracted filename + path, sha256sum/md5sum of the extracted file)
           
       NOTE: you can assume that if the checksum string is 32chars long it's an MD5SUM while if
             it is 64chars long it's a SHA256SUM.
             In practice the configuration used by rpmbuild can be found using:
                  grep -r filedigest /usr/lib/rpm
                  
            /usr/lib/rpm/macros:%_source_filedigest_algorithm    8
            /usr/lib/rpm/macros:%_binary_filedigest_algorithm    8

             Value "8" means that SHA256SUM will be used. Value "1" means MD5SUM.
             Other values of the filedigest_algorithm are unknown to me.
    """
    
    if not os.path.isfile(rpm_filename):
        print("No such file '{}'".format(rpm_filename))
        sys.exit(1)
    
    # we need an absolute path since we change the CWD in the subprocess:
    assert os.path.isabs(rpm_filename)
    try:
        # NOTE: regardless the query tag name "FILEMD5S", what is returned is actually a SHA256!
        rpm_checksums = subprocess.check_output(
            "rpm -qp --qf '[%{filenames},%{FILEMD5S}\n]' " + rpm_filename,
             stderr=subprocess.STDOUT,
             shell=True)
    except subprocess.CalledProcessError as e:
        print("Failed decompressing {}: {}\n".format(rpm_filename, e.output))
        sys.exit(3)

    # convert binary strings \n-separed -> string array
    rpm_files_comma_checksums = [s.strip().decode("utf-8") for s in rpm_checksums.splitlines()]
    
    # generate output
    retvalue = []
    for s in rpm_files_comma_checksums:
        filewithpath,checksum = s.split(',')
        if len(checksum)==0:
            continue    # if no checksum is present, this is a directory, skip it
        if len(checksum)!=32 and len(checksum)!=64:
            print("Found checksum of unexpected len ({} chars): {}. Expecting 32chars MD5SUMs or 64chars SHA256SUM.\n".format(len(checksum), checksum))
        
        assert os.path.isabs(filewithpath)
        retvalue.append( (filewithpath,checksum) )

    if verbose:
        print("The RPM file '{}' packages a total of {} files".format(rpm_filename, len(retvalue)))

    return retvalue

def match_checksum_pairs_with_fileystem(abs_filesystem_dir, rpm_checksum_pairs, strict_mode):
    """Walks given filesystem directory and searches for files matching those
       coming from an RPM packaged contents.
       Returns a list of filesystem full paths matching RPM contents and a list of
       files packaged in the RPM that could not be found:
           {filename_only:set(fullpath_to_file1,...) ... }
    """
    
    if not os.path.isdir(abs_filesystem_dir):
        print("No such directory '{}'".format(abs_filesystem_dir))
        sys.exit(1)
        
    # traverse root directory, and create an hashmap of the found files
    # this allows us to later search each packaged file in O(1)
    all_files_dict = {}
    nfound = 0
    for root, _, files in os.walk(abs_filesystem_dir):
        for filename_only in files:
            #print('---' + root + filename_only)
            nfound=nfound+1
            if filename_only in all_files_dict:
                all_files_dict[filename_only].add(root)
            else:
                all_files_dict[filename_only]=set([root])
            
    if verbose:
        print("** In folder '{}' recursively found a total of {} files".format(abs_filesystem_dir, nfound))

    # now try to match each RPM-packaged file with a file from previous hashmap
    # This takes O(n) where N=number of packaged files
    packaged_files_notfound = []
    packaged_files_fullpath = {}
    nfound = 0
    for rpm_file,rpm_checksum in rpm_checksum_pairs:
        rpm_fname = os.path.basename(rpm_file)
        file_matches = []
        packaged_files_fullpath[rpm_fname]=set()
        if rpm_fname in all_files_dict:
            # this RPM file has a file with the same name in the filesystem...
            dirname_set = all_files_dict[rpm_fname]
            for dirname in dirname_set:
                filesystem_fullpath = os.path.join(dirname,rpm_fname)
                if len(rpm_checksum)==32:
                    filesystem_checksum = md5_checksum(filesystem_fullpath)
                elif len(rpm_checksum)==64:
                    filesystem_checksum = sha256_checksum(filesystem_fullpath)
                if filesystem_checksum == rpm_checksum:
                    # ...and with the same checksum!
                    if verbose:
                        print("   Found a filesystem file '{}' in directory '{}' with same name and SHA256/MD5 sum of an RPM packaged file!".format(rpm_fname, dirname))
                    file_matches.append(filesystem_fullpath)
                
        if len(file_matches) == 0:
            packaged_files_notfound.append( (rpm_fname,rpm_checksum) )
        elif len(file_matches) == 1:
            packaged_files_fullpath[rpm_fname].add(file_matches[0])
            nfound=nfound+1
        else:
            assert len(file_matches)>1
            # add all the multiple matches
            for filesystem_fullpath in file_matches:
                packaged_files_fullpath[rpm_fname].add(filesystem_fullpath)
                nfound=nfound+1
                
            if verbose:
                # Emit a warning but keep going
                print("   WARNING: found an RPM packaged file '{}' that has the same name and SHA256/MD5 sum of multiple files found in the filesystem:".format(rpm_fname))
                for filesystem_fullpath in file_matches:
                    print("      {}    {}".format(filesystem_fullpath,rpm_checksum))
                    
            #if strict_mode:
            #print("This breaks 1:1 relationship. Aborting (strict mode).")
            #sys.exit(4)
            
    if verbose:
        print("   In folder '{}' recursively found a total of {} packaged files".format(abs_filesystem_dir, nfound))
    #return packaged_files_fullpath, packaged_files_notfound
    return packaged_files_fullpath

def generate_dependency_list(outfile, rpm_file, dict_matching_files, generate_empty_recipes):
    """Write a text file (typically the extension is ".d") in a format compatible with GNU
       make. The output text file, if included inside a Makefile, will instruct GNU make 
       about the dependencies of an RPM, so that such RPM can be rebuilt only when one of
       the dependencies is updated (rather than unconditionally).
    """
    #print(dict_matching_files)
    list_of_files = []
    for _,set_of_fullpaths in dict_matching_files.items():
        for fullpath in set_of_fullpaths:
            # IMPORTANT: GNU make dependencies cannot contain SPACES, at least in all GNU make versions <= 3.82;
            #            to work around this issue a smart way to proceed is just putting the ? wildcard instead of spaces: 
            list_of_files.append(fullpath.replace(' ', '?'))
            
    list_of_files = sorted(list_of_files)
    text = rpm_file + ": \\\n\t" + " \\\n\t".join(list_of_files) + "\n"
    
    if generate_empty_recipes:
        text += "\n\n# Empty recipes for dependency files (to avoid GNU make failures on dependency file removal):\n"
        for dep_filename in list_of_files:
            text += dep_filename + ":\n\n"
    
    try:
        with open(outfile, "w") as f:
            f.write(text)
    except:
        print("Failed writing to output file '{}'. Aborting".format(outfile))
        sys.exit(2)
    
    print("Successfully generated dependency list for '{}' in file '{}' listing {} dependencies".format(rpm_file, outfile, len(list_of_files)))

def generate_missed_file_list(outfile, rpm_file, packaged_files_notfound):
    """Write a text file with the list of packaged files that could not be found inside search folders.
       The text file is written in a simple CSV format
    """
    try:
        with open(outfile, "w") as f:
            f.write("File,SHA256SUM_or_MD5SUM\n")
            for fname,fname_checksum in packaged_files_notfound:
                f.write(("{},{}\n".format(fname,fname_checksum)))
    except (OSError, IOError) as e:
        print("Failed writing to output file '{}': {}. Aborting".format(outfile, e))
        sys.exit(2)
    
    print("Written list of packaged files not found in file '{}'".format(outfile))

def merge_two_dicts(x, y):
    #z = x.copy()   # start with x's keys and values
    #z.update(y)    # modifies z with y's keys and values & returns None
    #z = {**x, **y}
    #print(x)
    #print(y)
    
    z = {}
    for fname,set_fullpaths in x.items():
        z[fname]=set_fullpaths
    for fname,set_fullpaths in y.items():
        if fname in z:
            for fullpath in set_fullpaths:
                z[fname].add(fullpath)
        else:
            z[fname]=set_fullpaths
    return z

def usage():
    """Provides commandline usage
    """
    version = pkg_resources.require("rpm_make_rules_dependency_lister")[0].version
    print('rpm_make_rules_dependency_lister version {}'.format(version))
    print('Usage: %s [--help] [--strict] [--verbose] --input=somefile.rpm [--output=somefile.d] [--search=somefolder1,somefolder2,...]' % sys.argv[0])
    print('Required parameters:')
    print('  [-i] --input=<file.rpm>     The RPM file to analyze.')
    print('Main options:')
    print('  [-h] --help                 (this help)')
    print('  [-v] --verbose              Be verbose.')
    print('  [-o] --output=<file.d>      The output file where the list of RPM dependencies will be written;')
    print('                              if not provided the dependency file is written in the same folder of ')
    print('                              input RPM with .d extension in place of .rpm extension.')
    print('  [-s] --strict               Refuse to generate the output dependency file specified by --output if ')
    print('                              some packaged file cannot be found inside the search directories.')
    print('                              See also the --dump-missed-files option as alternative to --strict.')
    print('  [-m] --dump-missed-files=<file.csv>')
    print('                              Writes in the provided <file.csv> the list of files packaged in the RPM')
    print('                              that could not be found in the search directories.')
    print('  [-d] --search=<dir list>    The directories where RPM packaged files will be searched in (recursively);')
    print('                              this option accepts a comma-separated list of directories;')
    print('                              if not provided the files will be searched in the same folder of input RPM.')
    print('  [-e] --explicit-dependencies=<file1,file2,...>')
    print('                              Put the given list of filepaths in the output dependency file as explicit')
    print('                              dependencies of the RPM.')
    print('Advanced options:')
    print('  [-t] --strip-dirname        In the output dependency file strip the dirname of the provided RPM;')
    print('                              produces a change in output only if an absolute/relative path is provided')
    print('                              to --output option (e.g., if --output=a/b/c/myrpm.rpm is given).')
    print('  [-n] --no-empty-recipes')
    print('                              Disable generation of empty recipes for all dependency files.')
    print('                              Note that empty recipes are useful to avoid GNU make errors when a dependency')
    print('                              file is removed from the filesystem.')
    sys.exit(0)
    
    
# According to the GNU make User’s Manual section "Rules without Recipes or Prerequisites":
# If a rule has no prerequisites or recipe, and the target of the rule is a nonexistent file,
# then `make’ imagines this target to have been updated whenever its rule is run. 
# This implies that all targets depending on this one will always have their recipes run.


    
def parse_command_line():
    """Parses the command line
    """
    try:
        opts, remaining_args = getopt.getopt(sys.argv[1:], "ihvosmdetn", 
            ["input=", "help", "verbose", "output=", "strict", 
             "dump-missed-files=", "search=", "explicit-dependencies=",
             "strip-dirname", "no-empty-recipes"])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err))  # will print something like "option -a not recognized"
        usage()  # will exit program

    global verbose
    input_rpm = ""
    output_dep = ""
    search_dirs = ""
    missed_list_outfile = ""
    explicit_deps = ""
    strict = False
    strip_dirname = False
    generate_empty_recipes = True
    for o, a in opts:
        if o in ("-i", "--input"):
            input_rpm = a
        elif o in ("-h", "--help"):
            usage()
        elif o in ("-v", "--verbose"):
            verbose = True
        elif o in ("-s", "--strict"):
            strict = True
        elif o in ("-o", "--output"):
            output_dep = a
        elif o in ("-t", "--strip-dirname"):
            strip_dirname = True
        elif o in ("-d", "--search"):
            search_dirs = a
        elif o in ("-m", "--dump-missed-files"):
            missed_list_outfile = a
        elif o in ("-e", "--explicit-dependencies"):
            explicit_deps = a
        elif o in ("-n", "--no-empty-recipes"):
            generate_empty_recipes = False
        else:
            assert False, "unhandled option " + o + a

    if input_rpm == "":
        print("Please provide --input option (it is a required option)")
        sys.exit(os.EX_USAGE)

    abs_input_rpm = input_rpm
    if not os.path.isabs(input_rpm):
        abs_input_rpm = os.path.join(os.getcwd(), input_rpm)
        
    return {'spec_files': remaining_args,
            'input_rpm' : input_rpm,
            'abs_input_rpm' : abs_input_rpm,
            'output_dep' : output_dep,
            'search_dirs' : search_dirs,
            'strict': strict,
            'strip_dirname': strip_dirname,
            'missed_list_outfile': missed_list_outfile,
            "explicit_dependencies":explicit_deps,
            "generate_empty_recipes":generate_empty_recipes }

##
## MAIN
##

def main():
    config = parse_command_line()
    
    """Put all previous utility function in chain:
        - extracts RPM and computes SHA256 sums of contained files
        - matches those files with the folder where the RPM resides
        - generates the GNU make dependency list
    """
    search_dirs = config['search_dirs']
    if len(search_dirs)==0:
        # if not provided the search directory is the directory of input file
        search_dirs = [ os.path.dirname(config['abs_input_rpm']) ]
        if verbose:
            print("No search directory provided, using current directory '{}'".format(os.path.dirname(config['abs_input_rpm'])))
    else:
        search_dirs = search_dirs.split(',')
        
    if len(config['output_dep'])==0:
        # if not provided the output file lives in the same directory of input RPM
        # and is named like that RPM file just with .d extension
        input_rpm_dir = os.path.dirname(config['input_rpm'])
        input_rpm_filename = os.path.basename(config['input_rpm'])
        output_filename = os.path.splitext(input_rpm_filename)[0] + ".d"
        config['output_dep'] = os.path.join(os.getcwd(), os.path.join(input_rpm_dir, output_filename))
    
    rpm_file_checksums = get_checksum_pairs_from_rpm(config['abs_input_rpm'])
    
    dict_matching_files = {}
    for search_dir in search_dirs:
        a = match_checksum_pairs_with_fileystem(search_dir, rpm_file_checksums, config['strict'])
        dict_matching_files = merge_two_dicts(dict_matching_files,a)
        #packaged_files_notfound = packaged_files_notfound + b
    
    nfound = 0
    packaged_files_notfound = []
    for rpm_file,rpm_checksum in rpm_file_checksums:
        rpm_fname = os.path.basename(rpm_file)
        if rpm_fname not in dict_matching_files or len(dict_matching_files[rpm_fname])==0:
            packaged_files_notfound.append( (rpm_fname,rpm_checksum) )
        else:
            nfound = nfound+1
    
    # report all files not found all together at the end:
    if len(packaged_files_notfound)>0:
        if verbose or config['strict']:
            dirs = ",".join(search_dirs)
            print("Unable to find {} packaged files inside provided search folders {}. Files packaged and not found (with their SHA256 sum) are:".format(len(packaged_files_notfound), dirs))
            for fname,fname_checksum in packaged_files_notfound:
                print("   {}    {}".format(fname,fname_checksum))
        if len(config['missed_list_outfile'])>0:
            generate_missed_file_list(config['missed_list_outfile'], config['abs_input_rpm'], packaged_files_notfound)
        if config['strict']:
            print("Aborting output generation (strict mode)")
            sys.exit(3)
            
    if verbose:
        print("Found a total of {} packaged files across all search folders".format(nfound))
            
    input_rpm = config['input_rpm']
    if config['strip_dirname']:
        input_rpm = os.path.basename(input_rpm)
        
    # add explicit dependencies provided via command line:
    if len(config['explicit_dependencies'])>0:
        for filepath in config['explicit_dependencies'].split(','):
            filename_only = os.path.basename(filepath)
            if filename_only:
                if verbose:
                    print("Adding as explicit dependency: {}".format(filepath))
                if filename_only in dict_matching_files:
                    dict_matching_files[filename_only].add(filepath)
                else:
                    dict_matching_files[filename_only]=set([filepath])
        
    # finally generate the dependency listing:
    generate_dependency_list(config['output_dep'], input_rpm, dict_matching_files, config['generate_empty_recipes'])

if __name__ == '__main__':
    main()
