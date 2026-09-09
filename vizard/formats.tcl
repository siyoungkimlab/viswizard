############################################################
# formats.tcl -- DMS read/write and MAE write for VMD.
#
# VMD reads MAE (maeffplugin) but cannot write it, and has no DMS plugin at
# all; its Tcl has no sqlite3, so DMS cannot be done in Tcl.  These procs
# shell out to viswizard/pizard/formats.py, which handles both formats.
#
#   vizard_load_dms system.dms
#   vizard_write_mae "protein or resname LIG" out.mae
#   vizard_write_dms "protein or resname LIG" out.dms
############################################################

if {[info exists ::vizard_formats_loaded]} { return }
set ::vizard_formats_loaded 1

proc vizard_formats_py {} {
    set cands {}
    if {[info exists ::env(VIZARD_DIR)]} {
        lappend cands [file join $::env(VIZARD_DIR) .. pizard formats.py]
    }
    catch { lappend cands [file join [file dirname [file normalize [info script]]] \
                                     .. pizard formats.py] }
    lappend cands [file join $::env(HOME) viswizard pizard formats.py]
    foreach f $cands {
        if {$f ne "" && [file exists $f]} { return [file normalize $f] }
    }
    error "vizard: cannot find formats.py (looked in: $cands)"
}

proc vizard_python {} {
    foreach p {python3 python} {
        set x [lindex [auto_execok $p] 0]
        if {$x ne ""} { return $x }
    }
    error "vizard: no python3 on PATH"
}

proc vizard_load_dms {file args} {
    set tmp [file join [file dirname [file normalize $file]] \
                       "vizard_[pid].mae"]
    exec [vizard_python] [vizard_formats_py] [file normalize $file] $tmp
    set molid [eval mol new [list $tmp] type mae waitfor all $args]
    file delete $tmp
    puts "vizard: loaded $file as molid $molid ([molinfo $molid get numatoms] atoms)"
    return $molid
}

# dump the current frame of a selection, then let formats.py write the file
proc vizard_write {seltext out {molid top}} {
    if {$molid eq "top"} { set molid [molinfo top] }
    set s [atomselect $molid $seltext]
    if {[$s num] == 0} { $s delete ; error "vizard_write: '$seltext' matched 0 atoms" }
    set idx [$s get index]
    array set pos {}
    set k 0
    foreach i $idx { set pos($i) $k ; incr k }

    set dump [file join [file dirname [file normalize $out]] "vizard_[pid].vizdump"]
    set fh [open $dump w]
    set cell {0 0 0 0 0 0 0 0 0}
    if {![catch {lindex [pbc get -molid $molid -now] 0} c] && [lindex $c 0] > 2.0} {
        lassign $c a b cc
        set cell [list $a 0 0 0 $b 0 0 0 $cc]
    }
    puts $fh "CELL\t[join $cell \t]"
    foreach i $idx anum [$s get atomicnumber] nm [$s get name] rn [$s get resname] \
            ri [$s get resid] ch [$s get chain] sg [$s get segname] \
            xyz [$s get {x y z}] ms [$s get mass] q [$s get charge] {
        lassign $xyz x y z
        puts $fh "ATOM\t$anum\t$nm\t$rn\t$ri\t$ch\t$sg\t$x\t$y\t$z\t$ms\t$q"
    }
    set nb 0
    foreach i $idx bl [$s getbonds] ol [$s getbondorders] {
        foreach j $bl o $ol {
            if {$j <= $i || ![info exists pos($j)]} { continue }
            puts $fh "BOND\t$pos($i)\t$pos($j)\t[expr {int($o)}]"
            incr nb
        }
    }
    close $fh
    $s delete
    exec [vizard_python] [vizard_formats_py] $dump [file normalize $out]
    file delete $dump
    puts "vizard: wrote $out ([llength $idx] atoms, $nb bonds)"
    return $out
}

proc vizard_write_mae {seltext out {molid top}} { vizard_write $seltext $out $molid }
proc vizard_write_dms {seltext out {molid top}} { vizard_write $seltext $out $molid }
