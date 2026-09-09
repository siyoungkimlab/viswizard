############################################################
# glue.tcl -- keep unbonded components together across PBC.
#
#   source glue.tcl
#   glue_traj -glue "protein or resname LIG" -fit "protein and name CA"
#
# Orthorhombic cells.  For triclinic, project through the inverse
# cell matrix instead of dividing by {a b c}.
############################################################
package require pbctools

namespace eval ::Glue:: {
    namespace export glue_traj glue_strip glue_center
}

proc ::Glue::optimal_shifts {xs} {
    set n [llength $xs]
    if {$n < 2} { return [lrepeat $n 0] }
    set s {}; set y {}; set tot 0.0; set tot2 0.0
    foreach x $xs {                            ;# bring each into [-1/2, 1/2)
        set k 0
        while {$x <  -0.5} { set x [expr {$x + 1}]; incr k  1 }
        while {$x >=  0.5} { set x [expr {$x - 1}]; incr k -1 }
        lappend s $k; lappend y $x
        set tot  [expr {$tot  + $x}]
        set tot2 [expr {$tot2 + $x*$x}]
    }
    set xx [lsort -real $y]
    set v [expr {$n*$tot2 - $tot*$tot}]        ;# v(1)
    set best $v; set bestk 0
    for {set i 0} {$i < $n-1} {incr i} {
        set v [expr {$v + $n - 1 - 2*($tot + $i - $n*[lindex $xx $i])}]
        if {$v < $best} { set best $v; set bestk [expr {$i+1}] }
    }
    set left [lindex $xx $bestk]
    set out {}
    foreach x $y k $s {
        if {$x < $left} { incr k }
        lappend out $k
    }
    return $out
}

proc ::Glue::glue_traj {args} {
    # -join: which atoms to make whole.  Defaults to the glue selection.
    #   Joining every fragment costs ~22 s per 10 frames on a 32k-atom box
    #   because it walks all ~9700 waters; joining only what you display
    #   costs ~0.4 s.  Use "-join all" if you actually render solvent.
    array set opt {-molid top -glue "protein" -fit "protein and name CA" \
                   -wrap 1 -join "" -quiet 0}
    # -align is an alias for -fit
    if {[dict exists $args -align]} {
        set opt(-fit) [dict get $args -align]
        set args [dict remove $args -align]
    }
    array set opt $args
    set molid $opt(-molid)
    if {$molid eq "top"} { set molid [molinfo top] }

    set joinsel $opt(-join)
    if {$joinsel eq ""} { set joinsel $opt(-glue) }
    set gsel [atomselect $molid $opt(-glue)]
    set all  [atomselect $molid all]
    set fit  [atomselect $molid $opt(-fit)]
    set rest [atomselect $molid "not same fragment as ($opt(-glue))"]

    # connected components overlapping the glue selection = VMD fragments
    set frags [lsort -unique -integer [$gsel get fragment]]
    if {!$opt(-quiet)} {
        puts "glue: [$gsel num] atoms in [llength $frags] components; join='$joinsel'"
    }
    set t0 [clock milliseconds]
    foreach f $frags {
        lappend csel [atomselect $molid "($opt(-glue)) and fragment $f"]
        lappend msel [atomselect $molid "fragment $f"]
    }

    set nf [molinfo $molid get numframes]
    set nopbc_warned 0
    set ref [atomselect $molid $opt(-fit) frame 0]   ;# fit reference

    for {set n 0} {$n < $nf} {incr n} {
        # pbc join/wrap act on the MOLECULE's current frame, not the
        # selection's -- both have to be moved together.
        molinfo $molid set frame $n
        foreach s [concat $csel $msel [list $gsel $all $fit $rest]] { $s frame $n }
        lassign [lindex [pbc get -molid $molid -now] 0] a b c

        # A file with no periodic cell is not reported as zero: VMD hands back
        # a 1 x 1 x 1 A box.  Running the PBC steps on that shifts every atom
        # whose bond exceeds half a cell -- which is every atom -- and silently
        # destroys the structure.  Nothing here is meaningful without a real
        # cell, so do the alignment only.
        if {$a <= 2.0 || $b <= 2.0 || $c <= 2.0} {
            if {!$nopbc_warned} {
                puts [format "glue: no usable periodic cell (%.2f x %.2f x %.2f A) --\
                      skipping unwrap/glue/wrap, aligning only" $a $b $c]
                set nopbc_warned 1
            }
        } else {


            # 1. fix bonds: make each fragment whole.  -bondlist is NOT optional:
            # the default border-based path silently leaves molecules split.
            if {$joinsel eq "all"} {
                pbc join fragment -molid $molid -now -bondlist
            } elseif {$joinsel ne "none"} {
                pbc join fragment -molid $molid -now -bondlist -sel $joinsel
            }

            # 2. glue: shift whole components onto their optimal images
            foreach ax {0 1 2} L [list $a $b $c] {
                set fr {}
                foreach s $csel { lappend fr [expr {[lindex [measure center $s] $ax] / $L}] }
                lappend shifts [::Glue::optimal_shifts $fr]
            }
            foreach s $msel i [lindex $shifts 0] j [lindex $shifts 1] k [lindex $shifts 2] {
                if {$i || $j || $k} {
                    $s moveby [list [expr {$i*$a}] [expr {$j*$b}] [expr {$k*$c}]]
                }
            }
            unset shifts

            # 3. wrap everything else -- never the glued set, or step 2 is undone
            if {$opt(-wrap) && [$rest num]} {
                pbc wrap -molid $molid -now -center com -centersel $opt(-glue) \
                         -compound fragment -sel "not same fragment as ($opt(-glue))"
            }
        }

        # 4. fit on CA, last
        $all move [measure fit $fit $ref]
    }
    $ref delete
    foreach s [concat $csel $msel [list $gsel $all $fit $rest]] { $s delete }
    if {!$opt(-quiet)} {
        set dt [expr {([clock milliseconds]-$t0)/1000.0}]
        puts [format "glue: processed %d frames in %.2f s (%.0f ms/frame)" \
              $nf $dt [expr {1000.0*$dt/$nf}]]
    }
}

# Write out only what you care about, after gluing.  The result needs no
# processing when reloaded, and on a 32k-atom box it is ~9x smaller.
#
#   glue_traj -glue "protein or resname LIG" -fit "protein and name CA"
#   glue_strip -sel "protein or resname LIG" -o solute
#   # later:  vmd solute.pdb solute.dcd        (nothing left to do)
proc ::Glue::glue_strip {args} {
    array set opt {-molid top -sel "protein or resname LIG" -o solute}
    array set opt $args
    set molid $opt(-molid)
    if {$molid eq "top"} { set molid [molinfo top] }
    set s [atomselect $molid $opt(-sel)]
    if {[$s num] == 0} { error "glue_strip: selection '$opt(-sel)' matched 0 atoms" }
    $s writepdb $opt(-o).pdb
    animate write dcd $opt(-o).dcd sel $s waitfor all $molid
    puts "glue_strip: wrote $opt(-o).pdb and $opt(-o).dcd ([$s num] atoms,\
          [molinfo $molid get numframes] frames)"
    $s delete
}

# Frame the view on a subset of the representations.
#
# This reproduces, exactly, what you would do by hand: switch off the reps you
# do not want to frame on, press "=" (display resetview), then switch them back
# on.  resetview fits whatever is DISPLAYED, so the framing comes from VMD's own
# bounding-box logic rather than an approximation of it -- center of mass and a
# diagonal-based zoom give a visibly different result.
#
#   glue_center -reps {1 2}     ;# frame on reps 1 and 2, restore the rest
proc ::Glue::glue_center {args} {
    array set opt {-molid top -reps "" -keeprot 1}
    array set opt $args
    set molid $opt(-molid)
    if {$molid eq "top"} { set molid [molinfo top] }
    set n [molinfo $molid get numreps]
    if {$n == 0} { error "glue_center: molecule $molid has no representations" }

    set keep $opt(-reps)
    if {$keep eq ""} { for {set i 0} {$i < $n} {incr i} { lappend keep $i } }

    # Reps with "selupdate on" re-evaluate their selection on redraw, not on
    # the frame change itself.  Without this the pocket rep can still be
    # holding the selection from whatever frame the trajectory ended on, and
    # the framing comes out subtly wrong.
    catch {display update}

    set saved {}
    for {set i 0} {$i < $n} {incr i} { lappend saved [mol showrep $molid $i] }
    for {set i 0} {$i < $n} {incr i} {
        mol showrep $molid $i [expr {[lsearch -integer $keep $i] >= 0 ? "on" : "off"}]
    }
    # display resetview also resets the ROTATION, throwing away however the
    # user has oriented the molecule.  Zooming to something should not
    # reorient it, so save and restore the rotation.
    set saved_rot {}
    if {$opt(-keeprot)} {
        foreach m [molinfo list] { lappend saved_rot $m [molinfo $m get rotate_matrix] }
    }
    display resetview
    foreach {m rm} $saved_rot { molinfo $m set rotate_matrix $rm }
    for {set i 0} {$i < $n} {incr i} {
        mol showrep $molid $i [expr {[lindex $saved $i] ? "on" : "off"}]
    }
    # Without this the new matrices sit there until some other event forces a
    # redraw -- which is why the view only appeared after clicking in the
    # graphics window.
    catch {display update}
    catch {display update ui}
}

namespace import ::Glue::glue_traj ::Glue::glue_strip ::Glue::glue_center
