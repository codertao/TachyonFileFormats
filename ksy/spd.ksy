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

  Reverse-engineered from BORA05.SPX + space.exe. The SPED-object, placement
  and trigger sections and the QUAD/BDF fields are confirmed; header dwords
  0x1c/0x28 and the per-object record tails are only partially reversed and
  are left as unknowns. All section offsets are absolute file offsets
  (the engine relocates them by buf+0x1a4-first_offset at load).
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
  - id: unknown_1c
    type: u4
  - id: trigger_count
    type: u4
    doc: Number of mission triggers (Spx_RelocParamSection 0x48dac0).
  - id: trigger_offset
    type: u4
  - id: unknown_28
    type: u4
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
  dialog_count:
    pos: 0x58
    type: u4
  dialog_offset:
    pos: 0x5c
    type: u4
  scene_count:
    pos: 0x64
    type: u4
  scene_offset:
    pos: 0x68
    type: u4
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
      Variable-stride spawn record. Known fields are mapped; `stride` (at +0x02)
      is the total record size and is used to reach the next record. The region
      0x38..0x5c is per-kind payload (see `type_data`). Null records (kind 0)
      are only 0x38 bytes, so everything past `reserved_28` needs stride >= 0x60.
    seq:
      - id: kind
        type: u2
        doc: |
          Editor category tag (0=null 1=gate 2=roid/debris 3=ship/station
          4=MP pickup). Set by the editor; NOT read by the load path.
      - id: stride
        type: u2
        doc: Total size of this record in bytes.
      - id: sped_index
        type: s4
        doc: Index into the SPED-declaration section (`sped_objects`).
      - id: position
        type: vec3
        doc: World position x, y, z.
      - id: orientation
        type: vec3
        doc: |
          Euler angles; unit is 512 per full circle (0.703125 deg/unit):
          128 = 90deg, 256 = 180deg.
      - id: object_id
        type: s4
        doc: |
          Sector-unique object id. This is what trigger conditions/actions
          (OBJ category) and Sped_FindDef refer to.
      - id: flags
        type: u4
      - id: reserved_28
        size: 0x10
      - id: type_data
        size: 0x1c
        if: stride >= 0x60
        doc: |
          Per-kind payload (0x38..0x54). For ships/stations the first byte is
          the team/side. For gates (kind==1) it starts with a NUL-terminated
          destination .spx sector name.
      - id: group_id
        type: s4
        if: stride >= 0x60
        doc: |
          +0x54: trigger group id, or -1 for none (GROUP conditions/actions,
          Trig_SpawnGroup spawns every placement with this id).
      - id: type_data_58
        size: 4
        if: stride >= 0x60
        doc: Per-kind payload continued (0x58..0x5c).
      - id: unknown_5c
        type: s4
        if: stride >= 0x60
        doc: |
          Unknown (-1/0/10/11/13 seen). Earlier mislabelled "object id"; the id
          triggers use is `object_id` at +0x20.
      - id: rest
        size: 'stride - (stride >= 0x60 ? 0x60 : 0x38)'
        if: stride > 0x60 or (stride > 0x38 and stride < 0x60)
        doc: Undecoded tail padding out to `stride`.
    instances:
      team:
        value: type_data[0]
        if: stride >= 0x60
        doc: Team/side byte (meaningful when kind != 1).

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
          (waypoint reached) it is route<<16 | point.
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
          route<<16|point (NAV).
      - id: code
        type: u4
        doc: Action within the category (see notes/missions.md table).
      - id: arg2
        type: s4
        doc: |
          Parameter: value for VAR, start line for DIALOG, scene index for
          SCENE, target object for DOCK/ENTER_OBJ_BAY/spawn-by-class, side for
          CHANGE_RACE, route<<16 for CHANGE_WP, object id for ORDER actions.
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
