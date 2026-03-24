# FRPG2Paramdef
Library of DS2 paramdefs, and a C++ paramdex implementation for reading them.

## Writing Paramdefs
If you wish to contribute, please follow the same style used by the already existant params.
Internal names (the name field), should eirher be in camelCase or PascalCase. This is like a variable name, it should be descriptive but not redundant.
When giving a display name, do whatever you want but try to include unit of measures in square beackets when relevant (e.g. Mass [kg], Speed [m/s] etc)

## TODO
Params that need to be revised are:
* CHR_PARAM (see if groupType is an integer or was changed to a short)
* CHUNK_PHASE_PARAM 
* DUAL_WIELDING_PERMISSION_PARAM
* MAP_OBJECT_PARAM 
* MAP_OBJECT_PLAY_GO_DOOR_PARAM
* MAP_STATEACT_PARAM
* PLAYER_COMMON_PARAM
* WEAPON_TYPE_PARAM

Params that are unreferenced by the game:
* CAMERA_AREA_PARAM
* CAMERA_BATTLE_PARAM
* CAMERA_CONTROL_PARAM
* CAMERA_ELASTIC_PARAM
* EQUIP_REINFORCE_PARAM
