############################################################
# browse.tcl -- step through the loaded molecules from the keyboard.
#
#   browse             Up/Down in the graphics window switch molecule
#   browse off         show them all again, and hand the keys back
#   bnext / bprev      the same step, typed
#
# One molecule is shown at a time, framed on its ligand and pocket, which is
# the way to compare several of them when overlaying is just a thicket.  The
# view keeps its orientation -- they have been superposed by the time you get
# here -- so every structure is seen from the same angle.
#
# Up and Down are what VMD leaves free: most letters are taken (j/k and h/l
# rotate, g/G roll, r/t/s are mouse modes, x/y/z rock, +/- step frames), while
# the arrows only print a hint.  Whatever they were bound to is put back by
# "browse off".  The keys act while the mouse is over the graphics window.
############################################################
if {[info exists ::vizard_browse_loaded]} { return }
set ::vizard_browse_loaded 1

namespace eval ::VizardBrowse:: {
    variable mols {}
    variable i 0
    variable saved {}        ;# key -> what it did before
}

# Everything loaded, minus a --ref structure, which stays on as context.
proc ::VizardBrowse::molecules {} {
    set out {}
    foreach m [molinfo list] {
        if {[info exists ::vizard_ref] && $m == $::vizard_ref} continue
        if {[molinfo $m get numatoms] > 0} { lappend out $m }
    }
    return $out
}

proc ::VizardBrowse::binding {key} {
    foreach entry [user list keys] {
        if {[lindex $entry 0] eq $key} { return [lindex $entry 1] }
    }
    return ""
}

proc ::VizardBrowse::bind_keys {} {
    variable saved
    foreach {key cmd} {Down vizard_browse_next Up vizard_browse_prev} {
        dict set saved $key [binding $key]
        user add key $key $cmd
    }
}

proc ::VizardBrowse::unbind_keys {} {
    variable saved
    dict for {key prev} $saved {
        if {$prev ne ""} { catch { user add key $key $prev } }
    }
    set saved {}
}

proc ::VizardBrowse::show {{quiet 0}} {
    variable mols
    variable i
    # molecules can be deleted while browsing; drop them rather than error
    set live [molinfo list]
    set keep {}
    foreach m $mols { if {[lsearch -exact $live $m] >= 0} { lappend keep $m } }
    set mols $keep
    if {![llength $mols]} {
        puts "browse: nothing left to browse -- stopping"
        vizard_browse off
        return
    }
    set i [expr {$i % [llength $mols]}]
    set m [lindex $mols $i]
    foreach x $mols { mol off $x }
    mol on $m
    if {[info exists ::vizard_ref] && [lsearch -exact $live $::vizard_ref] >= 0} {
        mol on $::vizard_ref
    }
    mol top $m
    # reps 1 and 2 are the ligand and its pocket; a molecule without a ligand
    # has the cartoon alone
    set n [molinfo $m get numreps]
    set reps [expr {$n >= 3 ? {1 2} : ($n > 0 ? {0} : {})}]
    if {[llength $reps]} { catch { glue_center -molid $m -reps $reps } }
    if {!$quiet} {
        puts [format "browse: %d/%d  molid %-3s %s" [expr {$i + 1}] \
              [llength $mols] $m [molinfo $m get name]]
    }
}

proc ::VizardBrowse::step {delta} {
    variable mols
    variable i
    if {[llength $mols]} {
        incr i $delta
        show
    }
}

proc vizard_browse {{arg ""}} {
    set a [string tolower [string trim $arg]]
    if {$a in {-h --help help}} {
        puts {browse -- step through the loaded molecules.

  browse            start; Up/Down in the graphics window switch molecule
  browse off        stop, show every molecule again, hand the keys back

Down is the next molecule and Up the previous, both wrapping around.  bnext
and bprev do the same as commands, wherever the mouse is.  Each molecule is
shown alone and framed on its ligand and pocket; a --ref structure stays on
as context.}
        return
    }
    if {$a in {off stop}} {
        ::VizardBrowse::unbind_keys
        foreach m $::VizardBrowse::mols { catch { mol on $m } }
        set ::VizardBrowse::mols {}
        puts "browse: off -- every molecule is shown again"
        return
    }
    set mols [::VizardBrowse::molecules]
    if {![llength $mols]} { error "browse: no molecules are loaded" }
    set ::VizardBrowse::mols $mols
    set ::VizardBrowse::i 0
    if {![llength $::VizardBrowse::saved]} { ::VizardBrowse::bind_keys }
    ::VizardBrowse::show
    puts "browse: Up/Down over the graphics window step through [llength $mols]\
          molecules (bnext/bprev do it from here); 'browse off' when done"
}

proc vizard_browse_next {} { ::VizardBrowse::step 1 }
proc vizard_browse_prev {} { ::VizardBrowse::step -1 }

interp alias {} browse {} vizard_browse
interp alias {} bnext  {} vizard_browse_next
interp alias {} bprev  {} vizard_browse_prev
