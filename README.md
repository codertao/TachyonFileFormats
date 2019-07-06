# Goals

Provide a repository of documentation and source code for file formats used in the all time classic best game of all time "_Tachyon: The Fringe_". 

This is done mostly because I want to steal some of the resources for my own personal projects, but also because reverse engineering the file formats is a fun bit of archaeology. 

# File Types

* PFF
* SBF
* PCX
* OCF
* PAK
* etc


# PFF

PFF's are basically a giant tar file of all game assets- it's a format used across several NovaLogic games, probably to help save on disk space by decreasing file system overhead (a 1k texture doesn't need a 4k block and a filesystem entry). The version used in Tachyon doesn't support compressed content. The file has a header section, which includes the list of file entries, and then a nice soup of files catted together.

There are apparently at least 3 different versions of the file format, version 3, version 3, and version 4. Mostly differentiated by the size of the file entry- 32 bytes, 36 bytes, or 40 bytes. 

## Header



