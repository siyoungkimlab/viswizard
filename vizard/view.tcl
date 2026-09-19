############################################################
# view.tcl -- frame the view on a representation, a selection, or whatever
# atom you shift-click.
#
#   view 1 0               frame on rep 1 of molid 0
#   view {1 2} 0           frame on several reps
#   viewsel "resid 45"     frame on any selection
#   vizard_pick on         shift + left-click an atom to focus its residue
#
# All of these do what you would do by hand: switch off everything else,
# press "=" (display resetview, which fits only what is DISPLAYED), then
# switch the rest back on.
#
# NOTE: the command is not called "focus".  In a GUI session Tk is loaded and
# "focus" is Tk's own keyboard-focus command -- redefining it breaks VMD's
# menus.  It only looks unused in -dispdev text, where Tk is absent.
############################################################

if {[info exists ::vizard_view_loaded]} { return }
set ::vizard_view_loaded 1

proc vizard_focus {reps {molid top}} {
    if {$molid eq "top"} { set molid [molinfo top] }
    if {[info commands glue_center] eq ""} {
        error "vizard_focus: glue.tcl is not loaded"
    }
    set n [molinfo $molid get numreps]
    foreach r $reps {
        if {![string is integer -strict $r] || $r < 0 || $r >= $n} {
            error "vizard_focus: molid $molid has reps 0..[expr {$n-1}], got '$r'"
        }
    }
    glue_center -molid $molid -reps $reps
    return $reps
}

proc vizard_focus_sel {seltext {molid top}} {
    if {$molid eq "top"} { set molid [molinfo top] }
    set s [atomselect $molid $seltext]
    set na [$s num]
    $s delete
    if {$na == 0} { error "vizard_focus_sel: '$seltext' matched 0 atoms" }
    # a throwaway rep so resetview has something to fit on
    mol representation Points 1.0
    mol selection "$seltext"
    mol color ColorID 8
    mol addrep $molid
    set r [expr {[molinfo $molid get numreps] - 1}]
    if {[catch {glue_center -molid $molid -reps $r} err]} {
        mol delrep $r $molid
        error $err
    }
    mol delrep $r $molid
    return $na
}

proc vizard_pick_cb {args} {
    global vmd_pick_atom vmd_pick_mol vmd_pick_shift_state
    if {![info exists vmd_pick_atom] || ![info exists vmd_pick_mol]} { return }
    set m $vmd_pick_mol
    set i $vmd_pick_atom
    set shift 0
    if {[info exists vmd_pick_shift_state]} {
        set shift [expr {$vmd_pick_shift_state & 1}]
    }
    set s [atomselect $m "index $i"]
    if {[$s num] == 0} { $s delete ; return }
    set rn [lindex [$s get resname] 0] ; set ri [lindex [$s get resid] 0]
    set ch [lindex [$s get chain] 0]   ; set nm [lindex [$s get name] 0]
    $s delete
    if {$shift} {
        if {[catch {vizard_focus_sel "same residue as (index $i)" $m} e]} {
            puts "vizard: focus failed -- $e"
        } else {
            puts "vizard: focused $rn$ri chain $ch (picked $nm, molid $m)"
        }
    } else {
        puts "vizard: picked $rn$ri chain $ch $nm (molid $m, index $i)\
              -- hold shift to focus it"
    }
}

proc vizard_pick {{state on}} {
    global vmd_pick_atom
    catch { trace remove variable vmd_pick_atom write vizard_pick_cb }
    if {[lsearch -exact {on 1 yes true} [string tolower $state]] >= 0} {
        trace add variable vmd_pick_atom write vizard_pick_cb
        mouse mode pick
        puts "vizard: pick mode ON -- click an atom to identify it,\
              shift-click to focus its residue.  'vizard_pick off' to stop."
    } else {
        catch { mouse mode rotate }
        puts "vizard: pick mode off"
    }
}

# Shadows and ambient occlusion are recomputed on every redraw, so on a big
# enough system they cost something; vizard turns them on for the look, and
# this turns them off when the pace matters more than the picture.  Tachyon
# renders with whatever the display is set to, so vizard_movie turns them on
# for the render itself whatever the display says, and puts it back after.
proc vizard_ao {{state on}} {
    if {[lsearch -exact {on 1 yes true} [string tolower $state]] >= 0} {
        display shadows on
        display ambientocclusion on
        puts "vizard: shadows + ambient occlusion ON -- prettier, slower to redraw"
    } else {
        display shadows off
        display ambientocclusion off
        puts "vizard: shadows + ambient occlusion off -- quicker redraws"
    }
    catch {display update}
}

interp alias {} ao       {} vizard_ao
interp alias {} view     {} vizard_focus
interp alias {} focuson  {} vizard_focus
interp alias {} zoomto   {} vizard_focus
interp alias {} viewsel  {} vizard_focus_sel
interp alias {} focussel {} vizard_focus_sel
interp alias {} pick     {} vizard_pick
