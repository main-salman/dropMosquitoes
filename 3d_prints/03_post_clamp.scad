// ============================================================
// PART 3: Enclosure Post Clamp (x2 needed)
// Clamps IP67 enclosure to a 1" (25.4mm) aluminum pole.
// Two-piece design: base wraps pole, top bolts through
// enclosure mounting flange.
//
// Print: PETG or ABS, 100% infill, 0.2mm layer height
// Hardware: 2x M5 bolts + nuts per clamp (buy a small pack)
// Replaces: "U-Bolt Pipe Clamps" ($8 for 2)
// ============================================================

// --- Parameters ---
pole_dia       = 25.4;  // mm — 1 inch OD pole
pole_clearance = 0.4;   // mm — print tolerance
clamp_wall     = 5;     // mm — wall thickness around pole
clamp_width    = 30;    // mm — width of clamp along pole axis
flange_w       = 20;    // mm — bolt flange width each side
flange_t       = 5;     // mm — bolt flange thickness
bolt_dia       = 5.5;   // mm — M5 clearance

pole_r = (pole_dia + pole_clearance) / 2;
outer_r = pole_r + clamp_wall;

$fn = 80;

// Bottom half — wraps around lower half of pole
module clamp_bottom() {
    difference() {
        union() {
            // Half-cylinder cradle
            translate([0, 0, 0])
                difference() {
                    cylinder(h = clamp_width, r = outer_r);
                    translate([0, 0, -1])
                        cylinder(h = clamp_width + 2, r = pole_r);
                    // Cut top half off
                    translate([-outer_r - 1, 0, -1])
                        cube([outer_r*2 + 2, outer_r + 1, clamp_width + 2]);
                }
            
            // Bolt flanges (left and right)
            for (side = [-1, 1])
                translate([side * (outer_r + flange_w/2), -flange_t/2, 0])
                    cube([flange_w, flange_t, clamp_width], center=true);
        }
        
        // Bolt holes through flanges
        for (side = [-1, 1])
            translate([side * (outer_r + flange_w/2), 0, clamp_width/2])
                rotate([0, 0, 0])
                    cylinder(h = clamp_width + 2, d = bolt_dia, center=true);
    }
}

// Top half — mirror of bottom, bolts to enclosure
module clamp_top() {
    mirror([0, 1, 0])
        clamp_bottom();
}

// Show both halves
clamp_bottom();
translate([0, 0, clamp_width + 5])
    clamp_top();
