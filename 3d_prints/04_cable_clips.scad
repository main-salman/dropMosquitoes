// ============================================================
// PART 4: Cable Management Clips (print 10-20x)
// Snap-on clips for routing wires and tubing inside the IP67
// enclosure. Adhesive-backed or screw-mounted.
//
// Print: PLA or PETG, 100% infill, 0.15mm layer height
// Hardware: None (adhesive) or 1x M3 screw each
// Replaces: "Adhesive-Backed Zip Tie Mounts" ($9)
// ============================================================

// --- Parameters ---
clip_width    = 12;    // mm
clip_depth    = 15;    // mm
clip_height   = 10;    // mm
channel_dia   = 8;     // mm — fits 1/4" tubing (6.35mm OD) or wire bundle
wall          = 2;     // mm
snap_gap      = 4;     // mm — opening for snap-in
base_t        = 2;     // mm — base pad thickness
screw_hole    = 3.4;   // mm — M3 clearance (optional)

$fn = 40;

module cable_clip() {
    difference() {
        union() {
            // Base pad
            translate([-clip_width/2, -clip_depth/2, 0])
                cube([clip_width, clip_depth, base_t]);
            
            // C-shaped clip
            translate([0, 0, base_t])
                difference() {
                    cylinder(h = clip_width, d = channel_dia + wall*2);
                    translate([0, 0, -1])
                        cylinder(h = clip_width + 2, d = channel_dia);
                    // Snap opening at top
                    translate([-snap_gap/2, 0, -1])
                        cube([snap_gap, channel_dia, clip_width + 2]);
                }
        }
        
        // Optional screw hole through base
        translate([0, -clip_depth/4, -1])
            cylinder(h = base_t + 2, d = screw_hole);
    }
}

cable_clip();

// Show a row of 5 for batch printing
for (i = [1:4])
    translate([i * (clip_width + 4), 0, 0])
        cable_clip();
