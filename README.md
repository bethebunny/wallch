wallch
======

Random wallpaper setter with command line interface

======

### Installation

* Run `wallch.py <root_image_dir>` on login.
* Add `wallch` to your path.

======

### Random selection of commands

    wallch
    
Randomly switch to a different background

    wallch get
    
Get the location of the current background

    wallch add_dir ~/Pictures/walls
    wallch reload
    
Load new images

    wallch set ~/Pictures/walls/space.jpg
    
Set the current image to space.jpg

    wallch pause
    
Don't update the wallpaper until a `wallch play`

    wallch delay 10
    
Set the delay between wallpaper changes to 10 seconds

    wallch history
    
List a history of files displayed by wallch

    wallch errors
    
List files which your background program had problems setting (eg. dotfiles, misformatted images)

    wallch help
    
Show a description of all commands

======

### Features

* Works under python 2 and 3.
* Currently only supports [feh](https://wiki.archlinux.org/index.php/Feh) as a background setter
  * Designed to be modular. Feel free to add your own and push them.
