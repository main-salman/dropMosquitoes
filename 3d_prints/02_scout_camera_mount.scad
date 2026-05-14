// ============================================================
// PART 2: Scout Camera Mount Plate
// Mounts OV9281 camera module to inside of IP67 enclosure lid.
// Includes lens alignment hole and 4x standoff posts.
//
// Print: PETG, 80% infill, 0.2mm layer height
// Hardware: 4x M2 screws (camera PCB), 4x M3 screws (lid)
// Replaces: "M3 Nylon Standoff Assortment Kit" ($12)
// ============================================================

// --- Parameters ---
plate_w        = 36;    // mm — OV9281 PCB is ~32mm wide
plate_d        = 36;    // mm
plate_t        = 2.5;   // mm — base plate thickness
standoff_h     = 8;     // mm — clearance above lid for PCB components
standoff_od    = 6;     // mm
standoff_id    = 2.2;   // mm — M2 screw hole

// OV9281 mounting holes (center-to-center)
cam_mount_x    = 25;    // mm — measure your specific module
cam_mount_y    = 25;    // mm

// Lens clearance
lens_dia       = 14;    // mm — clear aperture for OV9281 lens

// Enclosure lid mounting holes (M3, wider spacing)
lid_mount_x    = 32;    // mm
lid_mount_y    = 32;    // mm
lid_hole_dia   = 3.4;   // mm — M3 clearance

$fn = 50;

module scout_mount() {
    difference() {
        union() {
            // Base plate
            translate([-plate_w/2, -plate_d/2, 0])
                cube([plate_w, plate_d, plate_t]);
            
            // 4x standoff posts
            for (x = [-cam_mount_x/2, cam_mount_x/2])
                for (y = [-cam_mount_y/2, cam_mount_y/2])
                    translate([x, y, plate_t])
                        cylinder(h = standoff_h, d = standoff_od);
        }
        
        // Lens hole through base
        translate([0, 0, -1])
            cylinder(h = plate_t + 2, d = lens_dia);
        
        // Camera screw holes through standoffs
        for (x = [-cam_mount_x/2, cam_mount_x/2])
            for (y = [-cam_mount_y/2, cam_mount_y/2])
                translate([x, y, -1])
                    cylinder(h = plate_t + standoff_h + 2, d = standoff_id);
        
        // Lid mounting holes (M3 countersunk)
        for (x = [-lid_mount_x/2, lid_mount_x/2])
            for (y = [-lid_mount_y/2, lid_mount_y/2])
                translate([x, y, -1])
                    cylinder(h = plate_t + 2, d = lid_hole_dia);
    }
}

scout_mount();
