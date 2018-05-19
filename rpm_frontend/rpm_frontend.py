#!/usr/bin/python3

#
# Purpose: Read an .rpm file and writes an output text file that, if included inside a 
#          Makefile, will instruct GNU make about the dependencies of the .rpm, so that 
#          such RPM can be rebuilt only when one of the dependencies is updated 
#          (rather than unconditionally) thus speeding up the time required by "make".
# Author: fmontorsi
# Creation: May 2018
#

import getopt, sys, os, subprocess
import tempfile, re, hashlib, shutil

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

def get_sha256sum_pairs(rpm_filename):
    """Extracts sha256sums from an RPM file and creates
       a list of pairs
           (extracted filename + path, sha256sum of the extracted file)
    """
    
    if not os.path.isfile(rpm_filename):
        print("No such file '{}'".format(rpm_filename))
        sys.exit(1)
    
    # we need an absolute path since we change the CWD in the subprocess:
    assert os.path.isabs(rpm_filename)
    try:
        # NOTE: regardless the query tag name "FILEMD5S", what is returned is actually a SHA256!
        rpm_sha256sums = subprocess.check_output(
            "rpm -qp --qf '[%{filenames},%{FILEMD5S}\n]' " + rpm_filename,
             stderr=subprocess.STDOUT,
             shell=True)
    except subprocess.CalledProcessError as e:
        print("Failed decompressing {}: {}\n".format(rpm_filename, e.output))
        sys.exit(3)

    # convert binary strings \n-separed -> string array
    rpm_files_comma_checksums = [s.strip().decode("utf-8") for s in rpm_sha256sums.splitlines()]
    
    # generate output
    retvalue = []
    for s in rpm_files_comma_checksums:
        filewithpath,sha256sum = s.split(',')
        if len(sha256sum)==0:
            continue    # if no checksum is present, this is a directory, skip it
        
        assert os.path.isabs(filewithpath)
        retvalue.append( (filewithpath,sha256sum) )

    if verbose:
        print("The RPM file '{}' packages a total of {} files".format(rpm_filename, len(retvalue)))

    return retvalue

def match_sha256sum_pairs_with_fileystem(abs_filesystem_dir, rpm_sha256sum_pairs):
    """Walks given filesystem directory and searches for files matching those
       coming from an RPM packaged contents.
       Returns a list of filesystem full paths matching RPM contents and a list of
       files packaged in the RPM that could not be found:
           [ fullpath_to_rpm_file, ... ]  [(filename1_notfound,sha256sum_filename1) ... ]
    """
    
    if not os.path.isdir(abs_filesystem_dir):
        print("No such directory '{}'".format(abs_filesystem_dir))
        sys.exit(1)
        
    # traverse root directory, and list directories as dirs and files as files
    all_files_dict = {}
    for root, dirs, files in os.walk(abs_filesystem_dir):
        #path = root.split(os.sep)
        #print((len(path) - 1) * '---', root, md5(root))
        for filename_only in files:
            #fullpath = os.path.join(root,file)
            #print(fullpath)
            #print(len(path) * '---', fullpath, md5(fullpath))
            all_files_dict[filename_only]=root
            
    if verbose:
        print("In folder '{}' recursively found a total of {} files".format(abs_filesystem_dir, len(all_files_dict.keys())))
    
    packaged_files_notfound = []
    packaged_files_fullpath = []
    for rpm_file,rpm_sha256sum in rpm_sha256sum_pairs:
        fname = os.path.basename(rpm_file)

        file_matched = False
        if fname in all_files_dict:
            dirname = all_files_dict[fname]
            filesystem_fullpath = os.path.join(dirname,fname)
            filesystem_sha256sum = sha256_checksum(filesystem_fullpath)
            if filesystem_sha256sum == rpm_sha256sum:
                if verbose:
                    print("Found a filesystem file '{}' in directory '{}' with same name and SHA256 sum of an RPM packaged file!".format(fname, dirname))
                packaged_files_fullpath.append(filesystem_fullpath)
                file_matched = True
                
        if not file_matched:
            packaged_files_notfound.append( (fname,rpm_sha256sum) )
    
    if verbose:
        print("In folder '{}' recursively found a total of {} packaged files".format(abs_filesystem_dir, len(packaged_files_fullpath)))
    return packaged_files_fullpath, packaged_files_notfound

def generate_dependency_list(outfile, rpm_file, list_of_files):
    """Write a text file (typically the extension is ".d") in a format compatible with GNU
       make. The output text file, if included inside a Makefile, will instruct GNU make 
       about the dependencies of an RPM, so that such RPM can be rebuilt only when one of
       the dependencies is updated (rather than unconditionally).
    """
    text = os.path.basename(rpm_file) + ": \\\n\t" + " \\\n\t".join(list_of_files) + "\n"
    try:
        with open(outfile, "w") as f:
            f.write(text)
    except:
        print("Failed writing to output file '{}'. Aborting".format(outfile))
        sys.exit(2)
    
    print("Successfully generated dependency list for '{}' in file '{}'".format(rpm_file, outfile))

def usage():
    """Provides commandline usage
    """
    print('Usage: %s [--help] [--strict] [--verbose] --input=somefile.rpm [--output=somefile.d] [--search=somefolder]' % sys.argv[0])
    print('Required parameters:')
    print('  [-i] --input=<file.rpm>     The RPM file to analyze.')
    print('Optional parameters:')
    print('  [-h] --help                 (this help)')
    print('  [-v] --verbose              Be verbose.')
    print('  [-s] --strict               Refuse to generate output dependency file is some packaged file cannot be')
    print('                              found inside the search folder.')
    print('  [-o] --output=<file.d>      The output file where the list of RPM dependencies will be written;')
    print('                              if not provided the dependency file is written in the same folder of ')
    print('                              input RPM with .d extension in place of .rpm extension.')
    print('  [-d] --search=<directory>   The directory where RPM packaged files will be searched in (recursively);')
    print('                              if not provided the files will be searched in the same folder of input RPM.')
    sys.exit(0)
    
def parse_command_line():
    """Parses the command line
    """
    try:
        opts, remaining_args = getopt.getopt(sys.argv[1:], "hvsios", ["help", "verbose", "strict", "input=", "output=", "search="])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(str(err))  # will print something like "option -a not recognized"
        usage()  # will exit program

    global verbose
    input_rpm = ""
    output_dep = ""
    search_dir = ""
    strict = False
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
        elif o in ("-v", "--verbose"):
            verbose = True
        elif o in ("-s", "--strict"):
            strict = True
        elif o in ("-i", "--input"):
            input_rpm = a
        elif o in ("-o", "--output"):
            output_dep = a
        elif o in ("-d", "--search"):
            search_dir = a
        else:
            assert False, "unhandled option " + o + a

    if input_rpm == "":
        print("Please provide --input option")
        sys.exit(os.EX_USAGE)

    abs_input_rpm = input_rpm
    if not os.path.isabs(input_rpm):
        abs_input_rpm = os.path.join(os.getcwd(), input_rpm)
        
    return {'spec_files': remaining_args,
            'input_rpm' : input_rpm,
            'abs_input_rpm' : abs_input_rpm,
            'output_dep' : output_dep,
            'search_dir' : search_dir,
            'strict': strict }

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
    
    if len(config['search_dir'])==0:
        # if not provided the search directory is the directory of input file
        config['search_dir'] = os.path.dirname(config['abs_input_rpm'])
        #print(config['search_dir'])
        
    if len(config['output_dep'])==0:
        # if not provided the output file lives in the same directory of input RPM
        # and is named like that RPM file just with .d extension
        input_rpm_dir = os.path.dirname(config['input_rpm'])
        input_rpm_filename = os.path.basename(config['input_rpm'])
        output_filename = os.path.splitext(input_rpm_filename)[0] + ".d"
        config['output_dep'] = os.path.join(os.getcwd(), os.path.join(input_rpm_dir, output_filename))
    
    pairs = get_sha256sum_pairs(config['abs_input_rpm'])
    matching_files, packaged_files_notfound = match_sha256sum_pairs_with_fileystem(config['search_dir'], pairs)
    
    if len(packaged_files_notfound)>0:
        print("Unable to find {} packaged files inside '{}'.".format(len(packaged_files_notfound), config['search_dir']))
        print("Files packaged and not found (with their SHA256 sum) are:")
        for fname,fname_sha256sum in packaged_files_notfound:
            print("   {}    {}".format(fname,fname_sha256sum))
        if config['strict']:
            print("Aborting output generation (strict mode)")
            sys.exit(1)
    
    generate_dependency_list(config['output_dep'], config['input_rpm'], matching_files)

if __name__ == '__main__':
    main()
