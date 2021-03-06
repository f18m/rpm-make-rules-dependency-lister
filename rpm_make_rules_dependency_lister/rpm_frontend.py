#!/usr/bin/env python3

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
    except FileNotFoundError:
        # this happens when a BROKEN symlink on the system matches the name of a file packaged inside an RPM
        return ""
    except IOError:
        print("Failed opening decompressed file '{}'\n".format(fname))
        sys.exit(3)

    return hash_md5.hexdigest()

def sha256_checksum(filename, block_size=65536):
    """Computes the SHA256 hash of a file on disk
    """
    sha256 = hashlib.sha256()
    try:
        with open(filename, 'rb') as f:
            for block in iter(lambda: f.read(block_size), b''):
                sha256.update(block)
    except OSError:
        # this happens when a directory is encountered
        return ""
    except FileNotFoundError:
        # this happens when a BROKEN symlink on the system matches the name of a file packaged inside an RPM
        return ""
    return sha256.hexdigest()

def get_permissions_safe(filename):
    try:
        return os.stat(filename).st_mode
    except FileNotFoundError as e:
        # this happens when a BROKEN symlink on the system matches the name of a file packaged inside an RPM
        if verbose:
            print("   Cannot stat the filename '{}': {}".format(filename, str(e)))
        return 0 # do not exit!

def is_executable(permission_int):
    """Takes a number containing a Unix file permission mode (as reported by RPM utility)
       and returns True if the file has executable bit set.
       
       NOTE: for some reason the modes returned by RPM utility are beyond 777 octal number...
             so we throw away the additional bits
    """
    executable_flag = 0x49  # 0x49 is equal to 0111 octal number, which is the flag for executable bits for USER,GROUP,OTHER
    return (permission_int & executable_flag) != 0

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


##
## MAIN CLASS
##

class RpmDependencyLister:
    
    def __init__(self):
        """Ctor"""
        self.tab_str = ' '
        self.tab_size = 4
        self.backup = False
    
    def get_checksum_tuples_from_rpm(self, rpm_filename):
        """Extracts sha256sums or md5sums from an RPM file and creates
           a list of N-tuples with:
               (extracted filename + path, sha256sum/md5sum of the extracted file, permissions of extracted filename, is_executable)
               
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
                "rpm -qp --qf '[%{filenames},%{FILEMD5S},%{FILEMODES}\n]' " + rpm_filename,
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
            filewithpath,checksum,permissions = s.split(',')
            if len(checksum)==0:
                continue    # if no checksum is present, this is a directory, skip it
            if len(checksum)!=32 and len(checksum)!=64:
                print("Found checksum of unexpected len ({} chars): {}. Expecting 32chars MD5SUMs or 64chars SHA256SUM.\n".format(len(checksum), checksum))
            
            permissions=int(permissions)
            
            assert os.path.isabs(filewithpath)
            retvalue.append( (filewithpath,checksum,permissions,is_executable(permissions)) )
    
        if verbose:
            print("The RPM file '{}' packages a total of {} files".format(rpm_filename, len(retvalue)))
    
        return retvalue
    
    def get_file_matches(self, rpm_fname, rpm_checksum, rpm_is_exec, filename2path_dict, filename2permission_dict, nameonly_check_for_exec_files):
        """Contains the logic that declares if a file packaged inside an RPM is matching a file
           found on the local filesystem.
           This function requires a pre-built dictionary (hashmap) of the files scanned in the local filesystem.
           
           Generally the matching is done based on just the MD5/SHA256sum but in case nameonly_check_for_exec_files=True,
           then the check is relaxed and is done on just the filename, for all executable files.
           
           Returns a list of matching files in the local filesystem.
        """
        file_matches = []
        if rpm_fname not in filename2path_dict:
            return file_matches
            
        # this RPM file has a file with the same name in the filesystem...
        dirname_list = filename2path_dict[rpm_fname]
        permission_list = filename2permission_dict[rpm_fname]
        assert len(dirname_list) == len(permission_list)
        
        for num_entries in range(0,len(dirname_list)):
            dirname = dirname_list[num_entries]
            filesystem_fullpath = os.path.join(dirname,rpm_fname)
            #filesystem_permissions = permission_list[num_entries]
            
            if nameonly_check_for_exec_files and rpm_is_exec:
                ##if is_executable(filesystem_permissions):
                if verbose:
                    print("   Found file '{}' in directory '{}' with same name and executable permissions of an RPM packaged file! Adding to dependency list.".format(rpm_fname, dirname))
                file_matches.append(filesystem_fullpath)
            else:
                if len(rpm_checksum)==32:
                    filesystem_checksum = md5_checksum(filesystem_fullpath)
                elif len(rpm_checksum)==64:
                    filesystem_checksum = sha256_checksum(filesystem_fullpath)
                if filesystem_checksum == rpm_checksum:
                    # ...and with the same checksum!
                    if verbose:
                        print("   Found file '{}' in directory '{}' with same name and SHA256/MD5 sum of an RPM packaged file! Adding to dependency list.".format(rpm_fname, dirname))
                    file_matches.append(filesystem_fullpath)
    
        return file_matches
    
    def match_checksum_tuples_with_fileystem(self, abs_filesystem_dirs, rpm_checksum_tuples, strict_mode, nameonly_check_for_exec_files):
        """Walks given filesystem directory list and searches for files matching those
           coming from an RPM packaged contents.
           Returns a list of filesystem full paths matching RPM contents and a list of
           files packaged in the RPM that could not be found:
               {filename_only:set(fullpath_to_file1,...) ... }
        """
        
        # traverse root directory, and create an hashmap of the found files
        # this allows us to later search each packaged file in O(1)
        filename2path_dict = {}
        filename2permission_dict = {}
        nfound = 0
        
        for abs_filesystem_dir in abs_filesystem_dirs:
            if not os.path.isdir(abs_filesystem_dir):
                print("No such directory '{}'".format(abs_filesystem_dir))
                sys.exit(1)
            for root, _, files in os.walk(abs_filesystem_dir):
                for filename_only in files:
                    #print('---' + root + filename_only)
                    nfound=nfound+1
                    permission_int = get_permissions_safe(os.path.join(root,filename_only))
                    if filename_only in filename2path_dict:
                        filename2path_dict[filename_only].append(root)
                        filename2permission_dict[filename_only].append(permission_int)
                    else:
                        filename2path_dict[filename_only] = [root]
                        filename2permission_dict[filename_only] = [permission_int]
                
        if verbose:
            print("** In folder '{}' recursively found a total of {} files".format(abs_filesystem_dir, nfound))
    
        # now try to match each RPM-packaged file with a file from previous hashmap
        # This takes O(n) where N=number of packaged files
        packaged_files_notfound = []
        packaged_files_fullpath = {}
        nfound = 0
        for rpm_file,rpm_checksum,rpm_permission,rpm_is_exec in rpm_checksum_tuples:
            rpm_fname = os.path.basename(rpm_file)
            packaged_files_fullpath[rpm_fname]=set()
            
            # query the dictionaries we just created and get N results back:
            file_matches = self.get_file_matches(rpm_fname, rpm_checksum, rpm_is_exec, filename2path_dict, filename2permission_dict, nameonly_check_for_exec_files)
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
    
    def generate_dependency_list(self, outfile, rpm_file, dict_matching_files, generate_empty_recipes):
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
        
        # According to the GNU make User’s Manual section "Rules without Recipes or Prerequisites":
        # If a rule has no prerequisites or recipe, and the target of the rule is a nonexistent file,
        # then `make’ imagines this target to have been updated whenever its rule is run. 
        # This implies that all targets depending on this one will always have their recipes run.
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
    
    def generate_missed_file_list(self, outfile, rpm_file, packaged_files_notfound):
        """Write a text file with the list of packaged files that could not be found inside search folders.
           The text file is written in a simple CSV format
        """
        if len(packaged_files_notfound)>0:
            try:
                with open(outfile, "w") as f:
                    f.write("File,SHA256SUM_or_MD5SUM\n")
                    for fname,fname_checksum in packaged_files_notfound:
                        f.write(("{},{}\n".format(fname,fname_checksum)))
            except (OSError, IOError) as e:
                print("Failed writing to output file '{}': {}. Aborting".format(outfile, e))
                sys.exit(2)
        else:
            try:
                # remove the file (in case it's there since a previous run)
                os.remove(outfile)
            except:
                # ignore errors in delete
                pass
        
        print("Written list of packaged files not found in file '{}'".format(outfile))
    
    def run(self, config):
        """Chains all together previous utility functions:
            - extracts from an RPM the MD5/SHA256 sums of contained files
            - matches those checksums with the search directories
            - generates the GNU make dependency list file
        """
        
        # STEP 1
        rpm_file_checksums = self.get_checksum_tuples_from_rpm(config['abs_input_rpm'])
        
        # STEP 2
        dict_matching_files = self.match_checksum_tuples_with_fileystem(config['search_dirs'], rpm_file_checksums, config['strict'], config['nameonly_check_for_exec_files'])
    
        nfound = 0
        packaged_files_notfound = []
        for rpm_file,rpm_checksum,rpm_permission,rpm_is_exec in rpm_file_checksums:
            rpm_fname = os.path.basename(rpm_file)
            if rpm_fname not in dict_matching_files or len(dict_matching_files[rpm_fname])==0:
                packaged_files_notfound.append( (rpm_fname,rpm_checksum) )
            else:
                nfound = nfound+1
        
        # report all files not found all together at the end:
        if len(config['missed_list_outfile'])>0:
            # generate or remove the list of missed file: 
            self.generate_missed_file_list(config['missed_list_outfile'], config['abs_input_rpm'], packaged_files_notfound)
        if len(packaged_files_notfound)>0:
            if verbose or config['strict']:
                dirs = ",".join(config['search_dirs'])
                print("Unable to find {} packaged files inside provided search folders {}. Files packaged and not found (with their SHA256 sum) are:".format(len(packaged_files_notfound), dirs))
                for fname,fname_checksum in packaged_files_notfound:
                    print("   {}    {}".format(fname,fname_checksum))
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
            
        # STEP 3: finally generate the dependency listing:
        self.generate_dependency_list(config['output_dep'], input_rpm, dict_matching_files, config['generate_empty_recipes'])
    
        print("Successfully generated dependency list for '{}' in file '{}' listing {} dependencies ({} packaged files are missing)".format(
            input_rpm, config['output_dep'], len(dict_matching_files.items()), len(packaged_files_notfound)))
    


##
## MAIN
##

def usage():
    """Provides commandline usage
    """
    version = pkg_resources.require("rpm_make_rules_dependency_lister")[0].version
    print('rpm_make_rules_dependency_lister version {}'.format(version))
    print('Typical usage:')
    print('  %s --input=somefile.rpm [--output=somefile.d] [--search=somefolder1,somefolder2,...]' % sys.argv[0])
    print('Required parameters:')
    print('  -i, --input=<file.rpm>     The RPM file to analyze.')
    print('Main options:')
    print('  -h, --help                 (this help)')
    print('  -v, --verbose              Be verbose.')
    print('      --version              Print version and exit.')
    print('  -o, --output=<file.d>      The output file where the list of RPM dependencies will be written;')
    print('                              if not provided the dependency file is written in the same folder of ')
    print('                              input RPM with .d extension in place of .rpm extension.')
    print('  -s, --strict               Refuse to generate the output dependency file specified by --output if ')
    print('                              some packaged file cannot be found inside the search directories.')
    print('                              See also the --dump-missed-files option as alternative to --strict.')
    print('  -m, --dump-missed-files=<file.csv>')
    print('                              Writes in the provided <file.csv> the list of files packaged in the RPM')
    print('                              that could not be found in the search directories.')
    print('  -d, --search=<dir list>    The directories where RPM packaged files will be searched in (recursively);')
    print('                              this option accepts a comma-separated list of directories;')
    print('                              if not provided the files will be searched in the same folder of input RPM.')
    print('  -e, --explicit-dependencies=<file1,file2,...>')
    print('                              Put the given list of filepaths in the output dependency file as explicit')
    print('                              dependencies of the RPM.')
    print('Advanced options:')
    print('  -x, --match-executable-by-name-only')
    print('                              By default the matching between RPM packaged files and file system files is')
    print('                              based on filename and MD5/SHA256 sums. This flag will loosen the match criteria')
    print('                              to the filename only, but only for files packages as executable. This is useful')
    print('                              in particular for ELF files that may be transformed by RPM macros during packaging.')
    print('  -t, --strip-dirname        In the output dependency file strip the dirname of the provided RPM;')
    print('                              produces a change in output only if an absolute/relative path is provided')
    print('                              to --output option (e.g., if --output=a/b/c/myrpm.rpm is given).')
    print('  -n, --no-empty-recipes')
    print('                              Disable generation of empty recipes for all dependency files.')
    print('                              Note that empty recipes are useful to avoid GNU make errors when a dependency')
    print('                              file is removed from the filesystem.')
    sys.exit(0)

    
def parse_command_line():
    """Parses the command line
    """
    try:
        opts, remaining_args = getopt.getopt(sys.argv[1:], "ihvosmdextn", 
            ["input=", "help", "verbose", "version", "output=", "strict", 
             "dump-missed-files=", "search=", "explicit-dependencies=",
             "match-executable-by-name-only", "strip-dirname", "no-empty-recipes"])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err))  # will print something like "option -a not recognized"
        usage()  # will exit program

    global verbose
    version = False
    input_rpm = ""
    output_dep = ""
    search_dirs = ""
    missed_list_outfile = ""
    explicit_deps = ""
    strict = False
    strip_dirname = False
    generate_empty_recipes = True
    match_exec_by_filename_only = False
    for o, a in opts:
        if o in ("-i", "--input"):
            input_rpm = a
        elif o in ("-h", "--help"):
            usage()
        elif o in ("-v", "--verbose"):
            verbose = True
        elif o in ("--version"):
            version = True
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
        elif o in ("-x", "--match-executable-by-name-only"):
            match_exec_by_filename_only = True
        else:
            assert False, "unhandled option " + o + a

    if version:
        version = pkg_resources.require("rpm_make_rules_dependency_lister")[0].version
        print("{}".format(version))
        sys.exit(0)

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
            "generate_empty_recipes":generate_empty_recipes,
            "nameonly_check_for_exec_files":match_exec_by_filename_only }


def main():
    if sys.version_info[0] < 3:
        # this is useful because on some systems with old versions of the "pip" utility you can download
        # this package using pip/Python2 even if this package is tagget with python_requires>=3: only
        # recent pip versions respect that tag! In case an old "pip" version was used tell the user:
        print('You need to run this with Python 3.')
        print('If you installed this package with "pip install" please uninstall it using "pip uninstall"')
        print('and reinstall it using "pip3 install" instead.')
        sys.exit(1)

    config = parse_command_line()
    
    # adjust list of search directories
    if len(config['search_dirs'])==0:
        # if not provided the search directory is the directory of input file
        config['search_dirs'] = [ os.path.dirname(config['abs_input_rpm']) ]
        if verbose:
            print("No search directory provided, using current directory '{}'".format(os.path.dirname(config['abs_input_rpm'])))
    else:
        # convert command-separated string to list:
        config['search_dirs'] = config['search_dirs'].split(',')
    
    # adjust output file name:
    if len(config['output_dep'])==0:
        # if not provided the output file lives in the same directory of input RPM
        # and is named like that RPM file just with .d extension
        input_rpm_dir = os.path.dirname(config['input_rpm'])
        input_rpm_filename = os.path.basename(config['input_rpm'])
        output_filename = os.path.splitext(input_rpm_filename)[0] + ".d"
        config['output_dep'] = os.path.join(os.getcwd(), os.path.join(input_rpm_dir, output_filename))
    
    # run core function:
    RpmDependencyLister().run(config)

if __name__ == '__main__':
    main()
