############################################################
# cg.tcl -- what element a coarse-grained bead stands for.
#
#   cgelem            give every bead the element it stands for
#   cgelem 1          the same, for molid 1
#
# A Martini or SIRAH file names beads, not atoms, and says nothing about
# elements, so VMD gives every bead element X, atomic number 0 and a radius
# picked off the first letter -- 1.9 A for "SC1", which is sulfur's.  Wrong
# elements mean wrong colours and wrong radii.
#
# The tables are the ones in pizard/cg.py; tests/test_cg.py checks that the
# two agree.  Keep them in step.
############################################################
if {[info exists ::vizard_cg_loaded]} { return }
set ::vizard_cg_loaded 1

namespace eval ::CG:: {}

# ion beads, which VMD would otherwise leave as element X
array set ::CG::IONS {NA Na SOD Na CL Cl CLA Cl K K POT K CA Ca CAL Ca MG Mg ZN Zn CES Cs CS Cs}
# Martini beads whose name says nothing about the element
array set ::CG::EXACT {BB C PO4 P NC3 N CNO N}
# prefix -> element, first match winning
set ::CG::PREFIX {SC C GL C W O C C D C}
# SIRAH names a bead for the atom it is centred on: the second letter
set ::CG::SIRAH_FIRST BG
set ::CG::SIRAH_ELEMENTS CNOSP
# any of these means the model is coarse-grained
set ::CG::MARKERS {BB GC GN SC1}
# atomic numbers, so the element and the number never disagree
array set ::CG::Z {H 1 C 6 N 7 O 8 Na 11 Mg 12 P 15 S 16 Cl 17 K 19 Ca 20 Zn 30 Cs 55}

proc ::CG::element {name} {
    variable IONS
    variable EXACT
    variable PREFIX
    variable SIRAH_FIRST
    variable SIRAH_ELEMENTS
    set n [string toupper [string trim $name]]
    if {$n eq ""} { return "" }
    if {[info exists IONS($n)]} { return $IONS($n) }
    if {[info exists EXACT($n)]} { return $EXACT($n) }
    if {[string length $n] >= 2
        && [string first [string index $n 0] $SIRAH_FIRST] >= 0
        && [string first [string index $n 1] $SIRAH_ELEMENTS] >= 0} {
        return [string index $n 1]
    }
    foreach {prefix elem} $PREFIX {
        if {[string first $prefix $n] == 0} { return $elem }
    }
    return ""
}

proc ::CG::coarse_grained {molid} {
    variable MARKERS
    set s [atomselect $molid all]
    set names [lsort -unique [$s get name]]
    $s delete
    foreach m $MARKERS {
        if {[lsearch -exact $names $m] >= 0} { return 1 }
    }
    return 0
}

# A bead is several atoms' worth of one, so it keeps the radius VMD gave it --
# only the element and its number are wrong, and those are what colouring and
# the Element category read.
proc vizard_cg_elements {{molid top} {quiet 0}} {
    variable ::CG::Z
    if {$molid eq "top"} { set molid [molinfo top] }
    set all [atomselect $molid all]
    set names [lsort -unique [$all get name]]
    $all delete
    set done 0
    foreach nm $names {
        set el [::CG::element $nm]
        if {$el eq ""} continue
        set s [atomselect $molid "name $nm"]
        $s set element $el
        if {[info exists ::CG::Z($el)]} { $s set atomicnumber $::CG::Z($el) }
        incr done [$s num]
        $s delete
    }
    if {!$quiet} {
        puts "cgelem: molid $molid -- gave $done beads the element they stand for"
    }
    return $done
}

# A coarse-grained file carries no bonds -- its beads sit ~3.5 A apart, past
# any distance-based bond search -- so VMD draws them as loose dots and its
# cartoon styles have nothing to follow.  Tube, Trace and Ribbons are no help
# either: they follow atoms named CA, and renaming a bead would break every
# selection that looks for it.  Bonding each backbone bead to the next one in
# its chain and drawing Licorice gives the same continuous backbone.
proc vizard_cg_bonds {{molid top} {quiet 0}} {
    if {$molid eq "top"} { set molid [molinfo top] }
    set bb [atomselect $molid "name BB GC"]
    if {[$bb num] < 2} { $bb delete ; return 0 }
    set all [atomselect $molid all]
    set bonds [$all getbonds]
    set idx [$bb list]
    set ch [$bb get chain]
    set rid [$bb get resid]
    set sg [$bb get segname]
    set added 0
    for {set i 0} {$i < [llength $idx] - 1} {incr i} {
        set j [expr {$i + 1}]
        # consecutive residues of one chain, so a gap stays a gap
        if {[lindex $ch $i] ne [lindex $ch $j]} continue
        if {[lindex $sg $i] ne [lindex $sg $j]} continue
        if {[lindex $rid $j] - [lindex $rid $i] != 1} continue
        set a [lindex $idx $i]
        set b [lindex $idx $j]
        if {[lsearch -exact [lindex $bonds $a] $b] >= 0} continue
        lset bonds $a [concat [lindex $bonds $a] $b]
        lset bonds $b [concat [lindex $bonds $b] $a]
        incr added
    }
    $all setbonds $bonds
    $all delete ; $bb delete
    if {!$quiet} {
        puts "cgbonds: molid $molid -- bonded $added backbone beads to the next"
    }
    return $added
}

interp alias {} cgelem  {} vizard_cg_elements
interp alias {} cgbonds {} vizard_cg_bonds
