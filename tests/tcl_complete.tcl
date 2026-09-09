# Check that every Tcl file is a syntactically complete script.
#
#     tclsh tests/tcl_complete.tcl vizard/*.tcl
#
# "info complete" catches unbalanced braces, brackets and quotes -- the errors
# that would otherwise only appear when VMD sources the file, and which -e
# reports without stopping.
set failed 0
foreach f $argv {
    set fh [open $f r]
    set src [read $fh]
    close $fh
    if {[info complete $src]} {
        puts "ok        $f"
    } else {
        puts "INCOMPLETE $f"
        set failed 1
    }
}
exit $failed
