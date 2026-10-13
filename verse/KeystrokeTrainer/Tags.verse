# Verse tags that let a lane find its own devices, so nothing has to be linked by hand in the
# Details panel. tools/build_map.py adds a Verse Tag Markup component with one of these tags to
# each helper device it places; the lane device picks the tagged device nearest to itself.

using { /Verse.org/Simulation/Tags }

# Trigger fired at the start of each rep of an exposure drill (wired to a guard's Spawn).
kt_pressure_tag<public> := class(tag){}
# Trigger fired when the lane's gun target or pickaxe target registers a hit.
kt_gun_hit_tag<public> := class(tag){}
kt_pickaxe_hit_tag<public> := class(tag){}
# Trigger that fires the lane's structure-clearing explosives. The lane fires it at the start of every set
# and rep, so earlier builds are gone and cannot satisfy a later check (stepping on the hub pad alone
# cleared once per visit, and auto-repeat never leaves the pad).
kt_clear_tag<public> := class(tag){}
# Marks a lane device so a section device can find it and play its drill. See Section.verse.
kt_lane_tag<public> := class(tag){}
# Optional metronome audio player.
kt_click_tag<public> := class(tag){}

kt_transport_test_tag := class(tag){}

kt_rift_node_tag := class(tag){}
kt_rift_router_tag := class(tag){}
kt_team_helper_tag := class(tag){}
kt_team_match_tag := class(tag){}
kt_drill_start_tag := class(tag){}
kt_team_nobuild_tag := class(tag){}
kt_team_queue_pad_tag := class(tag){}
kt_team_queue_device_tag := class(tag){}
kt_team_access_tag := class(tag){}
kt_team_point_tag := class(tag){}
kt_team_reboot_button_tag := class(tag){}
kt_team_ctf_base_tag := class(tag){}
kt_team_ammo_grant_tag := class(tag){}
kt_team_ammo_stock_tag := class(tag){}
kt_team_heal_stock_tag := class(tag){}
kt_rift_port_tag := class(tag){}
kt_lane_bot_tag := class(tag){}
kt_lane_granter_tag := class(tag){}
kt_sky_clear_tag := class(tag){}
