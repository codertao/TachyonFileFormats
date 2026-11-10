meta:
  id: spd
  title: Tachyon SPD / .SPX sector ("space") file
  file-extension: spx
  endian: le
  encoding: latin1
doc: |
  An .SPX file describes one sector of space for Tachyon: The Fringe: its
  backdrop, the SPED objects (ships / stations / gates / asteroids / ...) that
  populate it, their world placements, conditional sub-sector "stages", and
  links to adjacent sectors.

  The magic "SPD\x01" sits at offset +4; offset +0 is a leading dword
  (`first_offset`). The first 0x34 bytes are a small directory of
  {record-size, count, offset} triples pointing at the variable sections that
  follow, interleaved with two inline name strings (QUAD @0x34, BDF @0x78).

  The file also carries the sector's mission script: a trigger table
  (header +0x20/+0x24) of condition/action records, plus the dialog (.SCR) and
  cutscene (.SEN) name lists those triggers refer to. Job-specific missions
  live in the sub-sector SPX picked by `subsectors`.

  Reverse-engineered from BORA05.SPX + space.exe, with the label / route /
  spawn-list / alias / group / region-id / BaseWars fields cross-checked
  against NovaHQ's NovaResearch SPX write-up (and verified on all 302 files
  plus the engine where it reads them). Per-object record tails are only
  partially reversed. All section offsets are absolute file offsets (the
  engine relocates them by buf+0x1a4-first_offset at load).

  The header is variable length: `first_offset` is 0x1a4 (296 files), 0x11c
  (4) or 0x108 (2). Fields past the end of a short header are absent (the
  instances below are guarded on `first_offset`).

  Most sections use a {record size, count, offset} descriptor. The size
  dwords are constant across the shipped data: SPED 0x24, trigger 0x14,
  sub-sector 0x2c, dialog/scene 0x10, label/alias/group-name 0x20.
seq:
  - id: first_offset
    type: u4
  - id: magic
    contents: [0x53, 0x50, 0x44, 0x01]   # "SPD\x01"
  - id: sped_rec_size
    type: u4
    doc: Stride of one record in the SPED-declaration section.
  - id: sped_count
    type: u4
  - id: sped_offset
    type: u4
  - id: placement_count
    type: u4
  - id: placement_offset
    type: u4
  - id: trigger_rec_size
    type: u4
    doc: Stride of a trigger header (always 0x14). Descriptor for +0x20/+0x24.
  - id: trigger_count
    type: u4
    doc: Number of mission triggers (Spx_RelocParamSection 0x48dac0).
  - id: trigger_offset
    type: u4
  - id: subsector_rec_size
    type: u4
    doc: Stride of a sub-sector stage record (always 0x2c).
  - id: subsector_count
    type: u4
  - id: subsector_offset
    type: u4
instances:
  quad_name:
    pos: 0x34
    type: strz
    doc: Inline QUAD (galaxy quadrant) name.
  backdrop_name:
    pos: 0x78
    type: strz
    doc: Inline BDF backdrop name.
  dialog_rec_size:
    pos: 0x54
    type: u4
    doc: Always 0x10.
  dialog_count:
    pos: 0x58
    type: u4
  dialog_offset:
    pos: 0x5c
    type: u4
  scene_rec_size:
    pos: 0x60
    type: u4
    doc: Always 0x10.
  scene_count:
    pos: 0x64
    type: u4
  scene_offset:
    pos: 0x68
    type: u4
  label_rec_size:
    pos: 0x6c
    type: u4
    doc: Always 0x20.
  label_count:
    pos: 0x70
    type: u4
  label_offset:
    pos: 0x74
    type: u4
    doc: Relocated by Spx_LoadSector; consumer not identified yet.
  sector_flags:
    pos: 0x88
    type: u4
    doc: |
      bit 0 RADIATION: Sector_RadiationTick 0x460c20 deals 150 damage every
        16 ticks unless the ship has des flag +0x158 & 8 (radiation screen [l]).
      bit 1 FOG: Ent_SetQuadrant 0x4577d0 cuts the entity's sensor/visibility
        ranges (+0x15c/+0x160) to 3000 unless des flag +0x158 & 0x40
        (fog radar [l]). Gameplay fog, separate from the BDF's render fog.
  route_count:
    pos: 0x8c
    type: u4
    doc: Number of waypoint routes ("waygroups").
  route_offset:
    pos: 0x90
    type: u4
  kind2_count:
    pos: 0xa0
    type: u4
    doc: Number of placements with kind == 2 (holds in all 302 files). Editor bookkeeping.
  unknown_a4:
    pos: 0xa4
    type: u4
  target_rule_list_count:
    pos: 0xe8
    type: u4
    doc: Number of per-group AI target-rule lists (NovaResearch calls these spawn lists).
  target_rule_list_offset:
    pos: 0xec
    type: u4
  alias_rec_size:
    pos: 0xf0
    type: u4
    doc: Always 0x20.
  alias_count:
    pos: 0xf4
    type: u4
  alias_offset:
    pos: 0xf8
    type: u4
  region_id:
    pos: 0xfc
    type: u4
    if: first_offset >= 0x100
    doc: Galaxy region id; passed to the sector registry (FUN_00457e60) at load.
  sector_id:
    pos: 0x100
    type: u4
    if: first_offset >= 0x104
    doc: Sector id within the region (same call).
  group_name_rec_size:
    pos: 0x104
    type: u4
    if: first_offset >= 0x108
    doc: 0x20 when the group-name table is present.
  group_name_count:
    pos: 0x108
    type: u4
    if: first_offset >= 0x10c
  group_name_offset:
    pos: 0x10c
    type: u4
    if: first_offset >= 0x110
  reserved_110:
    pos: 0x110
    type: s4
    if: first_offset >= 0x114
    doc: Always -1.
  bw_base_sector:
    pos: 0x118
    type: u4
    if: first_offset >= 0x11c
    doc: BaseWars base sector (0 none, 1 Bora, 2 GalSpan) per NovaResearch; no reader found in space.exe.
  bw_base_race:
    pos: 0x11c
    type: u4
    if: first_offset >= 0x120
    doc: BaseWars base race (0 AGT/none, 1 Bora, 2 GalSpan) per NovaResearch; no reader found.
  labels:
    pos: label_offset
    type: strz
    size: label_rec_size
    repeat: expr
    repeat-expr: label_count
    doc: 32-byte mission/script labels (e.g. BFGF_05).
  routes:
    pos: route_offset
    type: route
    repeat: expr
    repeat-expr: route_count
    doc: |
      Waypoint routes. Placements pick their initial route by INDEX
      (placement +0x48, Nav_InitRoute 0x4349a0). Everything else uses the
      route TAG: waypoint-reached events post tag<<16 | point
      (Nav_ReachedWaypoint 0x4018a0), and CHANGE_WP / point action 0 go
      through Nav_FindRouteByTag 0x4058f0.
  target_rule_lists:
    pos: target_rule_list_offset
    type: target_rule_list
    repeat: expr
    repeat-expr: target_rule_list_count
    doc: |
      Per-group AI targeting rules. Spx_LinkSection 0x435690 stores each list
      in the quadrant's group slot for `group_id` (slot +0x18). When an AI
      ship of that group considers a target, Ai_TargetFilter 0x4012e0 runs
      the list (after the side-hostility check).
  aliases:
    pos: alias_offset
    type: strz
    size: alias_rec_size
    repeat: expr
    repeat-expr: alias_count
    if: alias_count > 0
    doc: AI/callsign alias names (e.g. "Python 1").
  group_names:
    pos: group_name_offset
    type: strz
    size: 0x20
    repeat: expr
    repeat-expr: group_name_count
    if: first_offset >= 0x110 and group_name_count > 0
    doc: Group / contact / base names (FG_*, CONT_*, ...).
  dialogs:
    pos: dialog_offset
    type: strz
    size: 0x10
    repeat: expr
    repeat-expr: dialog_count
    doc: |
      .SCR dialog scripts used by this sector (e.g. PLAYER.SCR). Indexed by
      trigger action PLAY_DIALOG `arg` and by DIALOG condition `sub`.
  scenes:
    pos: scene_offset
    type: strz
    size: 0x10
    repeat: expr
    repeat-expr: scene_count
    doc: |
      .SEN cutscenes, indexed by trigger action PLAY_SCENE `arg2`. The engine
      reads this list from the quadrant's main SPX.
  triggers:
    pos: trigger_offset
    type: trigger
    repeat: expr
    repeat-expr: trigger_count
    doc: |
      Mission triggers. Each is a list of conditions folded left to right
      (each condition's `join` says how it combines with the next one; no
      precedence) and a list of actions run when the result becomes true.
      A trigger fires once unless one of its conditions has the REPEATABLE
      flag. See decomp/notes/missions.md "Mission scripting".
  sped_objects:
    pos: sped_offset
    type: sped_object
    size: sped_rec_size
    repeat: expr
    repeat-expr: sped_count
    doc: |
      SPED ("SPace EDitor object") declarations. Each alias maps to a .des
      model via the SPED name registry; the .des DESC_TYPE selects the entity
      class (SHIP / ASTEROID / HYPER_GATE / STARBASE / ...).
  placements:
    pos: placement_offset
    type: placement
    repeat: expr
    repeat-expr: placement_count
    doc: |
      Per-object spawn records (the "def" fed to Sped_ConstructEntity). This is
      where world position and orientation actually live. Records are
      variable-length: each one's own `stride` field gives its size.
  subsectors:
    pos: subsector_offset
    type: subsector
    size: 0x2c
    repeat: expr
    repeat-expr: subsector_count
    doc: |
      Conditional sub-sector stages. The engine loads the first stage whose
      VarStore condition holds, so a sector can morph by mission variables.
types:
  sped_object:
    doc: |
      Read inside a `sped_rec_size`-byte window: an inline alias string
      followed by a runtime pointer at +0x20 (resolved at load; stale on disk).
    seq:
      - id: alias
        type: strz
        size: 0x20
      - id: runtime_ptr
        type: u4
        doc: Resolved at load time; meaningless on disk.
  placement:
    doc: |
      Variable-stride object record ("SPED def"). `stride` gives the size.
      A 0x38-byte common head, then a per-kind body:

        kind 0  (56 B)        null / marker records (flags 0x1002, never built)
        kind 1  (156/160 B)   hyper gate          -> placement_gate
        kind 2  (116 B)       asteroid / debris   -> placement_asteroid
        kind 3  (160/164 B)   AI object: ship, capital ship, starbase, mine,
                              cargo, beacon, speed ring -> placement_object
        kind 4  (116/120 B)   MP pickup / powerup -> placement_pickup

      The kind is set by the editor. The loader doesn't use it (the class
      comes from the SPED alias's .des), but Trig_SpawnGroup and
      TrigAct_GroupTakeoffNext only act on kind-3 records.
    seq:
      - id: kind
        type: u2
      - id: stride
        type: u2
        doc: Total size of this record in bytes.
      - id: sped_index
        type: s4
        doc: Index into `sped_objects` (-1 for kind 0).
      - id: position
        type: vec3
        doc: World position (16.16, same scale as PAK vertices).
      - id: orientation
        type: vec3
        doc: Euler angles, 512 units per turn (<<16 at runtime).
      - id: object_id
        type: s4
        doc: Sector-unique id used by triggers, Sped_FindDef and target rules.
      - id: flags
        type: u4
        doc: |
          Bits seen in code (names partly from NovaResearch):
          0x0001 use the player's current ship class (Sped_ConstructEntity)
          0x0002 label index refers to the MAIN SPX's label list, not the sub-sector's
          0x0004 ? (most common bit; no reader found)
          0x0008 don't spawn at sector load (wait for a trigger spawn)
          0x0010 start inactive (AI state 0xb)
          0x0020 passive: no engage limits / clears AI flag 1, group init without order
          0x0040 copied to entity +0xf6
          0x0080 has cargo contents (HUD shows `contents_name`)
          0x0200 gate: install proximity think fn (LAB_004263e0)
          0x0400 entity +0xc0 |= 0x20
          0x0800 gate object-id lookup (NovaResearch; unverified)
          0x1000 never constructed (kind-0 markers)
      - id: runtime_entity
        type: u4
        doc: Runtime entity pointer (+0x28); 0 on disk.
      - id: runtime_constructed
        type: u4
        doc: Runtime "constructed" latch (+0x2c); 0 on disk.
      - id: runtime_remapped
        type: u4
        doc: Runtime latch (+0x30) set once group/name ids are remapped; 0 on disk.
      - id: reserved_34
        type: u4
      - id: body
        size: stride - 0x38
        type:
          switch-on: kind
          cases:
            1: placement_gate
            2: placement_asteroid
            3: placement_object
            4: placement_pickup
  var_test:
    doc: |
      {s16 var section, s16 var key} into the player var store
      (Var_GetByIndex); section -1 = none.
    seq:
      - id: section
        type: s2
      - id: key
        type: s2
  placement_object:
    doc: |
      Kind-3 body (record +0x38..). Shared by every AI-object class; the
      class's sector-load routine (class +0x1c, e.g. FUN_00434e80 for ships)
      spawns it if `spawn_if` holds and flag 0x8 is clear, and the class
      constructor (class +0x2c, e.g. Sped_ConstructEntity) builds it.
    seq:
      - id: side
        type: u1
        doc: Side/team + 1 (0 = the .des default).
      - id: skill
        type: u1
        doc: AI skill + 1 (0 = .des default); +1 on the hardest difficulty, max 3.
      - id: bw_min_level
        type: u1
        doc: |
          BaseWars: starbase parts and mines only activate once their side's
          faction level >= this (message 0x1f from the faction-progress code,
          FUN_0040b5c0 / FUN_00433e80). 1 in many campaign files, where it is unused.
      - id: unknown_3b
        type: u1
      - id: spawn_if
        type: var_test
        doc: Spawn at sector load only if this var == `spawn_if_value` (FUN_004348d0).
      - id: spawn_if_value
        type: s4
      - id: label_index
        type: s4
        doc: |
          Index into the label list (main SPX if flags & 2, else this one), or
          -1. The entity is bound to that label (FUN_0041f590).
      - id: route_index
        type: s4
        doc: Initial waypoint route by INDEX (Nav_InitRoute), -1 = none.
      - id: route_point
        type: s4
        doc: Starting point in that route.
      - id: reserved_50
        type: u4
      - id: group
        type: s4
        doc: |
          Index into the SPX group-name table, -1 = none. At load
          (FUN_00434f10) the name is looked up in SHIPTEXT.BIN and rebased to
          [FLIGHT_GROUPS], giving the id triggers and target rules use.
      - id: unknown_58
        type: s4
        doc: 0..5, mostly on fighters. No reader found.
      - id: alias_index
        type: s4
        doc: |
          Index into `aliases` (callsign), -1 = none. Aliased ships keep their
          power/damage state across sector visits (FUN_00434630) and are not
          respawned once dead (FUN_004345f0).
      - id: contents_name
        type: s4
        doc: |
          Group-name-table index of the cargo contents (CONT_*), remapped to a
          SHIPTEXT key at load; shown on the HUD when flags & 0x80.
      - id: special_name
        type: s4
        doc: |
          Group-name-table index of the display name (COURAGE, STAR_PRINCESS,
          ...), remapped like `contents_name`. -1 = use "<group> <n>".
      - id: runtime
        size-eos: true
        doc: +0x68 wingman flag and other runtime state; zero on disk.
  placement_gate:
    doc: Kind-1 body. Gate_SpawnAndPreload 0x426400 (class +0x1c).
    seq:
      - id: destination
        type: strz
        size: 0x10
        doc: Destination .spx (local gates) or empty.
      - id: open_var
        type: var_test
        doc: |
          Var holding the open/closed state: open when its value >= 1
          (Gate_UpdateCollideState). TrigAct_GateSet writes it.
      - id: reserved_4c
        type: u4
      - id: flag_var
        type: var_test
        doc: If this var == 1, gate flag +0xe4 |= 1 (FUN_004262b0 / FUN_00426310).
      - id: unknown_54
        type: s4
        doc: Usually 1.
      - id: regional
        type: u4
        doc: |
          Nonzero = regional gate: no destination SPX is preloaded, jumping goes
          through Gate_JumpToSector, and `regional_dest` names the target.
      - id: regional_dest
        type: s4
        doc: |
          Regional destination, passed to Sector_Transition; its display name is
          ingame.bin record 0x7d + this.
      - id: reserved_60
        type: u4
      - id: unknown_64
        type: s4
        doc: -1 or small values; no reader found.
      - id: rest
        size-eos: true
  placement_asteroid:
    doc: Kind-2 body. Asteroid load spawn LAB_00407f30 (class +0x1c).
    seq:
      - id: scale
        type: s4
        doc: 16.16 scale; collision radius = int(scale) * .des radius.
      - id: rest
        size-eos: true
  placement_pickup:
    doc: Kind-4 body. Powerup spawn FUN_00456680.
    seq:
      - id: respawn_seconds
        type: s4
        doc: Respawn delay, x50 ticks (halved/doubled by the MP setting for type-10 pickups).
      - id: jitter
        type: s4
        doc: If nonzero, the pickup appears at a random offset of up to +-jitter*0x1000 per axis.
      - id: rest
        size-eos: true
  route:
    doc: 0x14-byte route ("waygroup") header.
    seq:
      - id: point_count
        type: u4
      - id: points_offset
        type: u4
      - id: tag
        type: s4
        doc: Id that triggers and CHANGE_WP use to name this route.
      - id: reserved
        size: 8
    instances:
      points:
        io: _root._io
        pos: points_offset
        type: route_point
        repeat: expr
        repeat-expr: point_count
  route_point:
    doc: 0x20-byte waypoint. Coordinates use the same units as placement positions.
    seq:
      - id: position
        type: vec3
      - id: action
        type: s4
        doc: |
          On-arrival action (Nav_RunWaypointAction 0x4017b0); other values
          (incl. -1) just advance to the next point, wrapping to the start:
          0 = change route to `param` (tag<<16|point), 1 = hyperspace out,
          2 = ACTIVATE, 3 = ENTERGATE `param` (or set the group's AI order
          to `param` if the ship is in a group), 4 = UNSPAWN.
      - id: param
        type: s4
      - id: unknown
        type: s4
        repeat: expr
        repeat-expr: 3
  target_rule_list:
    seq:
      - id: rec_size
        type: u4
        doc: Total size of this record (always 20); the next follows at +rec_size.
      - id: rule_size
        type: u4
        doc: Always 28.
      - id: group_id
        type: s4
        doc: |
          Final group id (index into SHIPTEXT.BIN [FLIGHT_GROUPS]), the same
          number trigger GROUP conditions/actions use.
      - id: rule_count
        type: u4
      - id: rules_offset
        type: u4
        doc: Absolute; relocated by Spx_LinkSection.
      - id: rest
        size: rec_size - 20
    instances:
      rules:
        io: _root._io
        pos: rules_offset
        type: target_rule
        size: rule_size
        repeat: expr
        repeat-expr: rule_count
  target_rule:
    doc: |
      One rule, evaluated by the predicate table at 0x53219c (index = type).
      Each returns bits: 1 = may attack, 4 = preferred (sets AI +0x324 = 2),
      2 = never attack (stops evaluation). The list's OR decides; a list with
      no matching rule forbids the target. Group match means the target's
      group slot id == target; object match means its placement object id ==
      target.
    seq:
      - id: type
        type: s4
        enum: target_rule_type
      - id: target
        type: s4
        doc: Group id or object id, depending on `type`.
      - id: runtime
        size: 20
        doc: Zero on disk.
  vec3:
    seq:
      - id: x
        type: s4
      - id: y
        type: s4
      - id: z
        type: s4
  subsector:
    doc: |
      0x2c-byte conditional stage. Loaded when its VarStore condition holds.
      var[section,key] indexes the player var store; [0,4] is
      player_main_vars.CURRENT_JOB (enum 'jobs').
    seq:
      - id: name
        type: strz
        size: 0x10
      - id: var_section
        type: s4
      - id: var_key
        type: s4
      - id: value
        type: s4
      - id: op
        type: s4
        doc: 0 = AND-eq, 1 = AND-neq, 2 = OR.
      - id: var2_section
        type: s4
      - id: var2_key
        type: s4
      - id: value2
        type: s4
  trigger:
    doc: |
      0x14-byte trigger header. `conditions_offset` / `actions_offset` are
      absolute file offsets.
    seq:
      - id: condition_count
        type: u4
      - id: action_count
        type: u4
      - id: fired
        type: u4
        doc: Runtime latch (set when the trigger fires); 0 on disk.
      - id: conditions_offset
        type: u4
      - id: actions_offset
        type: u4
    instances:
      conditions:
        io: _root._io
        pos: conditions_offset
        type: condition
        repeat: expr
        repeat-expr: condition_count
      actions:
        io: _root._io
        pos: actions_offset
        type: action
        repeat: expr
        repeat-expr: action_count
  condition:
    doc: |
      0x28-byte condition. Matches a game event {category, sub, code, value,
      a, b}: category/sub/code must be equal; value is compared with >= for
      the (category, code) pairs listed in `value_uses_ge`, otherwise ==.
      VAR conditions are level-sensitive (re-tested on every var change);
      all other conditions stay satisfied once their event has happened.
    seq:
      - id: category
        type: u4
        enum: cond_category
      - id: sub
        type: u4
        doc: |
          Subject: object id (OBJ), group id (GROUP), var category<<16|index
          (VAR), dialog-list index (DIALOG), side byte (SIDE), else 0.
      - id: code
        type: u4
        doc: Event code within the category (see notes/missions.md table).
      - id: value
        type: s4
        doc: |
          Compared against the event value. For PLAYER code 1 (proximity) the
          engine multiplies this by 10 at load. For OBJ code 5 / GROUP code 2
          (waypoint reached) it is route TAG<<16 | point index (see `routes`).
      - id: a
        type: s4
        doc: Extra key, matched only when flags & 2 (a=1 means `b` is an object id).
      - id: b
        type: s4
        doc: Extra key, usually an object id (e.g. the object docked with / picked up).
      - id: join
        type: u4
        enum: cond_join
        doc: How this condition's result combines with the NEXT condition.
      - id: flags
        type: u4
        doc: |
          bit 0 MOMENTARY  (counts only in the frame it was satisfied)
          bit 1 MATCH_AB   (event a/b must also equal `a`/`b`)
          bit 2 REPEATABLE (trigger re-arms after firing)
      - id: satisfied
        type: u4
        doc: Runtime; 0 on disk.
      - id: satisfied_frame
        type: u4
        doc: Runtime; 0 on disk.
    instances:
      var_category:
        value: sub >> 16
        doc: For VAR conditions, the vars.cfg var_categories index (20 = COUNTERS, 21 = MISSION_VARS).
      var_index:
        value: sub & 0xffff
      momentary:
        value: (flags & 1) != 0
      match_ab:
        value: (flags & 2) != 0
      repeatable:
        value: (flags & 4) != 0
      value_uses_ge:
        value: '(category == cond_category::player and code == 0) or (category == cond_category::object and (code == 3 or code == 4)) or (category == cond_category::enemies and code == 1) or (category == cond_category::group and code == 1)'
        doc: |
          True where the engine's comparator table (0x559984) uses
          event value >= condition value. VAR conditions compare by code
          instead (0/1 ==, 2 >, 3 <).
  action:
    doc: |
      0x10-byte action, dispatched through the engine table 0x559c48
      [category][code] = {fn, extra}. Categories 12..14 run past that
      12-entry table and alias into category 11 (codes +1/+2/+3).
    seq:
      - id: category
        type: s4
        enum: action_category
        doc: -1 = empty slot.
      - id: arg
        type: u4
        doc: |
          Subject: object id (OBJECT, GATE), group id (GROUP), var
          category<<16|index (VAR, COUNTER), dialog-list index (DIALOG),
          region<<16|sector (NAV: sets DESTINATION_REGION/SECTOR, Nav_SetDestination 0x437610).
      - id: code
        type: u4
        doc: Action within the category (see notes/missions.md table).
      - id: arg2
        type: s4
        doc: |
          Parameter: value for VAR, start line for DIALOG, scene index for
          SCENE, target object for DOCK/ENTER_OBJ_BAY/spawn-by-class, side for
          CHANGE_RACE, route tag<<16 | point for CHANGE_WP, object id for ORDER actions.
enums:
  cond_category:
    0: player
    1: object
    2: gate
    3: var
    4: enemies
    5: group
    6: unknown_6
    7: dialog
    8: side
  cond_join:
    0: join_and
    1: join_and_not
    2: join_or
  target_rule_type:
    0: attack_any
    1: attack_group
    2: attack_object
    3: prefer_group
    4: prefer_object
    5: ignore_group
    6: ignore_object
    7: none_7
    8: none_8
    9: ignore_players
  action_category:
    -1: none
    0: gate
    1: var
    2: play_dialog
    3: play_scene
    4: counter
    5: object
    6: group
    7: nav
    8: order_add
    9: order_remove
    10: order_complete
    11: all_quadrants
    12: order_remove_all
    13: order_complete_all
    14: all_quadrants_14
