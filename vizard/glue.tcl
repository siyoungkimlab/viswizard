############################################################
# glue.tcl -- keep unbonded components together across PBC.
#
#   source glue.tcl
#   glue_traj -glue "protein or resname LIG" -fit "protein and name CA"
#
# Orthorhombic cells.  For triclinic, project through the inverse
# cell matrix instead of dividing by {a b c}.
#
# A long trajectory is split across several VMD processes (-workers), each
# gluing a consecutive range of frames; the ranges are loaded back in order.
############################################################
package require pbctools

namespace eval ::Glue:: {
    namespace export glue_traj glue_strip glue_center
    # parallel workers source this file again; [info script] only means
    # something while the file is being sourced
    variable here [file dirname [file normalize [info script]]]
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

# Making fragments whole.  "pbc join -bondlist" walks every atom in Tcl and
# rebuilds the whole coordinate list for each bond -- ~75 ms/frame for a
# 4.8k-atom protein.  Instead: a BFS spanning tree of the selection's bonds,
# built once (the topology never changes), then one pass per frame that
# moves only atoms whose bond to their parent crosses the box.  Same result,
# ~7x faster.
#
# Returns flat {parent child ...} positions within the selection, every
# parent before its children.
proc ::Glue::tree_prepare {molid seltext} {
    set sel [atomselect $molid $seltext]
    set idx [$sel list]
    set bonds [$sel getbonds]
    $sel delete
    set i 0
    foreach a $idx { set pos($a) $i; incr i }
    set n $i
    set seen [lrepeat $n 0]
    set edges {}
    for {set s 0} {$s < $n} {incr s} {
        if {[lindex $seen $s]} continue
        lset seen $s 1
        set queue [list $s]; set qi 0
        while {$qi < [llength $queue]} {
            set p [lindex $queue $qi]; incr qi
            foreach b [lindex $bonds $p] {
                if {![info exists pos($b)]} continue    ;# bond leaves the selection
                set c $pos($b)
                if {[lindex $seen $c]} continue
                lset seen $c 1
                lappend edges $p $c
                lappend queue $c
            }
        }
    }
    return $edges
}

proc ::Glue::tree_join {sel edges a b c} {
    set crd [$sel get {x y z}]
    set ha [expr {0.5*$a}]; set hb [expr {0.5*$b}]; set hc [expr {0.5*$c}]
    foreach {p ch} $edges {
        lassign [lindex $crd $p] px py pz
        lassign [lindex $crd $ch] x y z
        set dx [expr {$x-$px}]; set dy [expr {$y-$py}]; set dz [expr {$z-$pz}]
        if {abs($dx) > $ha || abs($dy) > $hb || abs($dz) > $hc} {
            # lset on an unshared list is in place, unlike lreplace
            lset crd $ch [list [expr {$x - $a*round($dx/$a)}] \
                               [expr {$y - $b*round($dy/$b)}] \
                               [expr {$z - $c*round($dz/$c)}]]
        }
    }
    $sel set {x y z} $crd
}

# Steps 1-3 on one frame.  The selections must already be on that frame, and
# so must the MOLECULE: pbc wrap acts on its current frame, not the selections'.
proc ::Glue::pbc_steps {molid a b c jsel edges csel msel wrap centersel wrapsel} {
    # 1. fix bonds: make each fragment whole
    if {$jsel ne ""} { tree_join $jsel $edges $a $b $c }

    # 2. glue: shift whole components onto their optimal images
    foreach ax {0 1 2} L [list $a $b $c] {
        set fr {}
        foreach s $csel { lappend fr [expr {[lindex [measure center $s] $ax] / $L}] }
        lappend shifts [optimal_shifts $fr]
    }
    foreach s $msel i [lindex $shifts 0] j [lindex $shifts 1] k [lindex $shifts 2] {
        if {$i || $j || $k} {
            $s moveby [list [expr {$i*$a}] [expr {$j*$b}] [expr {$k*$c}]]
        }
    }

    # 3. wrap everything else -- never the glued set, or step 2 is undone
    if {$wrap} {
        pbc wrap -molid $molid -now -center com -centersel $centersel \
                 -compound fragment -sel $wrapsel
    }
}

proc ::Glue::glue_traj {args} {
    # -join: which atoms to make whole.  Defaults to the glue selection;
    #   vizard never draws solvent, so joining it is wasted work.  Use
    #   "-join all" if you actually render solvent, "-join none" to skip.
    # -workers: VMD processes to split the frames across.  "auto" uses one
    #   per CPU (up to 8) when there are enough frames; 1 = this VMD only.
    array set opt {-molid top -glue "protein" -fit "protein and name CA" \
                   -wrap 1 -join "" -quiet 0 -workers auto}
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
    set nf [molinfo $molid get numframes]
    set t0 [clock milliseconds]

    # connected components overlapping the glue selection = VMD fragments
    set gsel [atomselect $molid $opt(-glue)]
    set frags [lsort -unique -integer [$gsel get fragment]]
    if {!$opt(-quiet)} {
        puts "glue: [$gsel num] atoms in [llength $frags] components; join='$joinsel'"
    }

    # Several VMDs at once.  Only with a real cell: without one there is
    # nothing to do but the fit, which is cheap.
    set nw [nworkers $opt(-workers) $nf]
    lassign [molinfo $molid get {a b c} frame 0] a b c
    if {$nw > 1 && $a > 2.0 && $b > 2.0 && $c > 2.0} {
        if {[catch {parallel $molid [array get opt] $joinsel $nw} err]} {
            puts "glue: parallel run failed -- $err"
            puts "glue: gluing in this VMD instead"
        } else {
            $gsel delete
            if {!$opt(-quiet)} {
                set dt [expr {([clock milliseconds]-$t0)/1000.0}]
                puts [format "glue: processed %d frames in %.2f s on %d VMD processes" \
                      $nf $dt $err]
            }
            return
        }
    }

    set all  [atomselect $molid all]
    set fit  [atomselect $molid $opt(-fit)]
    set rest [atomselect $molid "not same fragment as ($opt(-glue))"]
    set csel {}; set msel {}
    foreach f $frags {
        lappend csel [atomselect $molid "($opt(-glue)) and fragment $f"]
        lappend msel [atomselect $molid "fragment $f"]
    }
    set jsel ""; set edges {}
    if {$joinsel ne "none"} {
        set jsel [atomselect $molid $joinsel]
        set edges [tree_prepare $molid $joinsel]
    }
    set wrap [expr {$opt(-wrap) && [$rest num] > 0}]
    set wrapsel "not same fragment as ($opt(-glue))"

    set nopbc_warned 0
    set ref [atomselect $molid $opt(-fit) frame 0]   ;# fit reference

    for {set n 0} {$n < $nf} {incr n} {
        molinfo $molid set frame $n
        foreach s [concat $csel $msel [list $gsel $all $fit $rest] $jsel] { $s frame $n }
        lassign [molinfo $molid get {a b c}] a b c

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
            pbc_steps $molid $a $b $c $jsel $edges $csel $msel \
                      $wrap $opt(-glue) $wrapsel
        }

        # 4. fit on CA, last
        $all move [measure fit $fit $ref]
    }
    $ref delete
    foreach s [concat $csel $msel [list $gsel $all $fit $rest] $jsel] { $s delete }
    if {!$opt(-quiet)} {
        set dt [expr {([clock milliseconds]-$t0)/1000.0}]
        puts [format "glue: processed %d frames in %.2f s (%.0f ms/frame)" \
              $nf $dt [expr {1000.0*$dt/max($nf,1)}]]
    }
}

# ---- parallel gluing -------------------------------------------------------
#
# This VMD writes its frames to one DCD and starts N headless VMDs, each of
# which loads the same structure file, glues a consecutive range of frames
# (steps 1-3) and writes it back out.  The ranges are then loaded back into
# the molecule IN RANGE ORDER, which is what keeps the frame order, and the
# fit is done here.  Loading and writing 1000 frames of a 47k-atom box takes
# ~0.3 s, so nearly all of the time is the gluing itself.
#
# The workers load the original structure file because writing the structure
# out does not survive the trip: the js and psf writers drop bonds VMD
# guessed, and with the bonds put back VMD still assigns fragments
# differently.  Anything that depends on the topology is therefore decided
# here and shipped as atom indices, and every worker checks that its
# fragments are exactly ours before touching a frame.  Any failure leaves the
# molecule as it was and glue_traj carries on in this VMD.

proc ::Glue::ncpu {} {
    foreach c {{sysctl -n hw.ncpu} {nproc} {getconf _NPROCESSORS_ONLN}} {
        if {![catch {exec {*}$c 2>@1} n] && [string is integer -strict [string trim $n]]
            && [string trim $n] > 0} {
            return [string trim $n]
        }
    }
    if {[info exists ::env(NUMBER_OF_PROCESSORS)]} { return $::env(NUMBER_OF_PROCESSORS) }
    return 1
}

proc ::Glue::nworkers {want nf} {
    # Past ~8 workers the gain flattens (memory bandwidth), and each worker
    # costs ~0.3 s to start and load, so give each at least 25 frames.
    if {$want eq "auto"} { set want [expr {min([ncpu], 8)}] }
    if {![string is integer -strict $want] || $want < 1} {
        error "-workers must be auto or a positive integer, got '$want'"
    }
    return [expr {max(1, min($want, $nf / 25))}]
}

proc ::Glue::tempdir {} {
    set base [expr {$::tcl_platform(platform) eq "windows" ? "C:/Windows/Temp" : "/tmp"}]
    foreach v {TMPDIR TEMP TMP} {
        if {[info exists ::env($v)] && [file isdirectory $::env($v)]} {
            set base $::env($v); break
        }
    }
    set dir [file join $base viswizard_glue_[pid]_[clock clicks]]
    file mkdir $dir
    return $dir
}

# returns the number of workers used; errors leave the molecule untouched
proc ::Glue::parallel {molid optlist joinsel nw} {
    set topfile [lindex [molinfo $molid get filename] 0 0]
    set toptype [lindex [molinfo $molid get filetype] 0 0]
    if {$topfile eq "" || ![file readable $topfile]} {
        error "the structure file is not on disk to hand to the workers"
    }
    set dir [tempdir]
    set rc [catch {parallel_run $molid $optlist $joinsel $nw $topfile $toptype $dir} res]
    catch {file delete -force $dir}
    if {$rc} { error $res }
    return $res
}

proc ::Glue::parallel_run {molid optlist joinsel nw topfile toptype dir} {
    variable here
    array set opt $optlist
    set nf [molinfo $molid get numframes]

    set gsel [atomselect $molid $opt(-glue)]
    set gidx [$gsel list]
    set cidxs {}; set midxs {}
    foreach f [lsort -unique -integer [$gsel get fragment]] {
        set s [atomselect $molid "($opt(-glue)) and fragment $f"]
        lappend cidxs [$s list]; $s delete
        set s [atomselect $molid "fragment $f"]
        lappend midxs [$s list]; $s delete
    }
    $gsel delete
    set jidx {}; set edges {}
    if {$joinsel ne "none"} {
        set s [atomselect $molid $joinsel]; set jidx [$s list]; $s delete
        set edges [tree_prepare $molid $joinsel]
    }
    set s [atomselect $molid "not same fragment as ($opt(-glue))"]
    set wrap [expr {$opt(-wrap) && [$s num] > 0}]
    $s delete
    set s [atomselect $molid all]; set frag [$s get fragment]; $s delete

    animate write dcd [file join $dir frames.dcd] waitfor all $molid
    set fh [open [file join $dir job.tcl] w]
    puts $fh [list set ::Glue::job [dict create topfile $topfile toptype $toptype \
        gidx $gidx cidxs $cidxs midxs $midxs jidx $jidx edges $edges \
        frag $frag wrap $wrap]]
    close $fh

    # consecutive ranges; chunk k holds frames first..last
    set per [expr {($nf + $nw - 1) / $nw}]
    set null [expr {$::tcl_platform(platform) eq "windows" ? "NUL" : "/dev/null"}]
    set pipes {}
    for {set first 0} {$first < $nf} {incr first $per} {
        set last [expr {min($first + $per, $nf) - 1}]
        set cmd [list [info nameofexecutable] -dispdev text \
                      -e [file join $here glue_worker.tcl] \
                      -args [file join $here glue.tcl] $dir [llength $pipes] $first $last]
        # stdin from /dev/null: a worker must never read this VMD's terminal
        lappend pipes [open "|$cmd < $null 2>@1" r]
    }
    # all workers are running; collect them in order
    set failed {}
    set k 0
    foreach p $pipes {
        set out [read $p]
        catch {close $p}
        if {![string match "*GLUE WORKER $k DONE*" $out]} {
            set why "worker $k gave no result"
            foreach line [split $out \n] {
                if {[string match "GLUE WORKER $k ERROR:*" $line]} { set why $line }
            }
            lappend failed $why
        }
        incr k
    }
    if {[llength $failed]} { error [join $failed "; "] }
    for {set i 0} {$i < $k} {incr i} {
        if {![file exists [file join $dir chunk_$i.dcd]]} { error "chunk $i is missing" }
    }

    # Replace the frames, range by range, in order.  Should that fail, put
    # the originals back before giving up.
    animate delete all $molid
    if {[catch {
        for {set i 0} {$i < $k} {incr i} {
            mol addfile [file join $dir chunk_$i.dcd] type dcd waitfor all $molid
        }
        set got [molinfo $molid get numframes]
        if {$got != $nf} { error "reloaded $got of $nf frames" }
    } err]} {
        animate delete all $molid
        mol addfile [file join $dir frames.dcd] type dcd waitfor all $molid
        error $err
    }

    # 4. fit, last
    set all [atomselect $molid all]
    set fit [atomselect $molid $opt(-fit)]
    set ref [atomselect $molid $opt(-fit) frame 0]
    for {set n 0} {$n < $nf} {incr n} {
        $all frame $n; $fit frame $n
        $all move [measure fit $fit $ref]
    }
    $all delete; $fit delete; $ref delete
    return $k
}

# Run by glue_worker.tcl in a headless VMD, with ::Glue::job from job.tcl.
proc ::Glue::worker_run {dir k first last} {
    variable job
    dict with job {}
    set m [mol new $topfile type $toptype waitfor all]
    animate delete all $m
    mol addfile [file join $dir frames.dcd] type dcd first $first last $last \
                waitfor all $m
    set all [atomselect $m all]
    if {[$all get fragment] ne $frag} {
        error "fragments differ from the main VMD's"
    }
    set csel {}; set msel {}
    foreach c $cidxs mm $midxs {
        lappend csel [atomselect $m "index $c"]
        lappend msel [atomselect $m "index $mm"]
    }
    set jsel [expr {[llength $jidx] ? [atomselect $m "index $jidx"] : ""}]
    set centersel "index $gidx"
    set wrapsel "not same fragment as (index $gidx)"
    set nf [molinfo $m get numframes]
    for {set n 0} {$n < $nf} {incr n} {
        molinfo $m set frame $n
        foreach s [concat $csel $msel [list $all] $jsel] { $s frame $n }
        lassign [molinfo $m get {a b c}] a b c
        if {$a > 2.0 && $b > 2.0 && $c > 2.0} {
            pbc_steps $m $a $b $c $jsel $edges $csel $msel $wrap $centersel $wrapsel
        }
    }
    animate write dcd [file join $dir chunk_$k.dcd] waitfor all $m
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
