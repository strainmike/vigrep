import os
import argparse
import locale
from contextlib import contextmanager, redirect_stderr

from pylabview.LVrsrcontainer import VI
from pylabview import LVheap

from tqdm import tqdm


class FakeParseOptions:
    """HACK pylabview expects an Options argument to be passed in
    to everything containing the configuration the user specified.
    Its not intended to be used directly as classes.
    """

    def __init__(self, file):
        self.file = file

    @property
    def verbose(self):
        return 0

    @property
    def print_map(self):
        return False

    @property
    def typedesc_list_limit(self):
        return 4095

    @property
    def array_data_limit(self):
        return (2**28) - 1

    @property
    def store_as_data_above(self):
        return 4095

    @property
    def store_as_data_above(self):
        return 4095

    @property
    def filebase(self):
        return os.path.splitext(os.path.basename(self.file))[0]

    @property
    def rsrc(self):
        return self.file

    @property
    def xml(self):
        return self.file

    @property
    def keep_names(self):
        return True

    @property
    def raw_connectors(self):
        return True


@contextmanager
def suppress_stderr():
    """A context manager that redirects stderr to devnull"""
    with open(os.devnull, "w") as fnull:
        with redirect_stderr(fnull) as err:
            yield (err)
    # yield(None)


def get_text_from_heap(heap):
    plaintext = ""
    for i, heap_object in enumerate(heap):
        scopeInfo = heap_object.getScopeInfo()
        tagName = LVheap.tagEnToName(heap_object.tagEn, heap_object.parent)
        if "text" == tagName:
            try:
                plaintext += (
                    heap_object.content.decode(locale.getpreferredencoding()) + "\n"
                )
            except UnicodeDecodeError:
                print("failed decode:" + str(heap_object.content))
    return plaintext


def get_vi_plaintext(path):
    plaintext = ""
    with open(path, "rb") as rsrc_fh:
        po = FakeParseOptions(path)
        # HACK: pylabview isn't really intended to be called programatically, we accept that API changes
        # could break us
        vi = VI(po)
        # HACK: skipping part of the ctor here to avoid parsing all sections of the file
        # pylabview can't parse everything and over half our VIs throw while parsing sections
        # that we don't care about for this use.
        vi.dataSource = "rsrc"
        vi.rsrc_fh = rsrc_fh
        vi.src_fname = rsrc_fh.name
        vi.rsrc_map = []
        vi.readRSRCList(rsrc_fh)
        block_headers = vi.readRSRCBlockInfo(rsrc_fh)
        filtered_block_headers = []
        # currently we only search the front panel and block diagram for strings
        for header in block_headers:
            section_name = bytearray(header.ident).decode()
            if "FPH" in section_name:
                filtered_block_headers.append(header)
            elif "BDH" in section_name:
                filtered_block_headers.append(header)
        vi.readRSRCBlockData(rsrc_fh, filtered_block_headers)
        vi.checkSanity()
        # TODO see what else shows up in the main XML and parse that
        # root = vi.exportXMLRoot()
        for block in vi.blocks.values():
            for section_num, section in block.sections.items():
                root = section
                parent_elems = []
                elem = None
                if getattr(section, "objects", None):
                    plaintext += get_text_from_heap(section.objects)

    return plaintext


def walk_and_parse_files(root_dir, to_find):
    failed_to_parse = 0
    files_to_check = []
    for currentpath, folders, files in os.walk(root_dir):
        for file in files:
            filename, file_extension = os.path.splitext(file)
            if ".vi" == file_extension:
                file_path = os.path.join(currentpath, file)
                files_to_check.append(file_path)
    for file_path in tqdm(files_to_check):
        try:
            with suppress_stderr():
                file_text = get_vi_plaintext(file_path)
            # print(file_text)
            # print(file_path)
            if to_find in file_text:
                tqdm.write(file_path)
        except KeyboardInterrupt:
            raise
        except:
            failed_to_parse += 1
            raise
    print(
        "failed to parse:"
        + str(failed_to_parse)
        + " out of "
        + str(len(files_to_check))
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pattern", action="store")
    parser.add_argument("file", action="store")

    options = parser.parse_args()
    walk_and_parse_files(options.file, options.pattern)


if __name__ == "__main__":
    main()
