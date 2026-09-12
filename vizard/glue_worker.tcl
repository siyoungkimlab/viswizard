############################################################
# glue_worker.tcl -- one of glue_traj's parallel workers; not for direct use.
#
#   vmd -dispdev text -e glue_worker.tcl -args GLUE_TCL DIR K FIRST LAST
#
# Glues frames FIRST..LAST of DIR/frames.dcd and writes DIR/chunk_K.dcd.
# glue.tcl's path is an argument because [info script] is empty under -e.
############################################################
lassign $argv gluetcl dir k first last
if {[catch {
    source $gluetcl
    source [file join $dir job.tcl]
    ::Glue::worker_run $dir $k $first $last
} err]} {
    puts "GLUE WORKER $k ERROR: $err"
} else {
    puts "GLUE WORKER $k DONE"
}
quit
