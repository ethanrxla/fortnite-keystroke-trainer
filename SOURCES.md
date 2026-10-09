# What we built on, and why (checked 2026-10-06)

## Connecting Claude Code and Codex to UEFN

| Option | License | State | Verdict |
|---|---|---|---|
| **Epic UEFN MCP** (built into UEFN, beta since 2026-08-20) | Epic's UEFN terms | Official, maintained. Verse read/write/compile, devices, Scene Graph, play sessions, logs. Local HTTP `127.0.0.1:8000/mcp`. Known issues: XYZ vs Left-Up-Forward coordinates, editor hitches on heavy calls, play-in-client only. | **Use.** No install; works with Claude Code and Codex (streamable HTTP, no flags). |
| **ViggoJonssonF/uefn-claude-automation** | MIT | 1 commit, 0 stars, says verified on UEFN 42.00 (Sept 2026). Unattended playtest loop, Verse AutoTest harness, health check, client screenshots, Codex delegation. | **Use**, pinned to `b250768`. Very new and single-author, so we pin and review before bumping. Our `AutoTest.verse` adapts its harness. |
| KirChuvakov/uefn-mcp-server | MIT | ~69 stars, 5 commits. In-editor Python listener (port 8765) + external MCP server, 22 to 28 tools. Predates Epic's MCP. | **Optional escape hatch** for raw editor Python that Epic's toolsets don't expose. Not needed to start. |
| TheGahbi/uefn-mcp-server | MIT (fork of KirChuvakov) | 0 stars, 9 commits. Bridges Epic's tools + 28 native ones. | Skip; same idea, less proven. |
| undergroundrap/UEFN-TOOLBELT | **AGPL-3.0** | ~48 stars, active (v2.4.1). 362 editor Python tools + own MCP bridge. | Skip for now. Powerful, but AGPL obligations and some network-reaching features; revisit if we need procedural arena tools. |
| quangdang46/uefn-verse-mcp | **AGPL-3.0** + attribution | **Archived 2026-07-15.** | Avoid. |
| Generic Unreal MCPs (ChiR24/Unreal_mcp, uemcp, etc.) | various | Target full UE5 editor plugins/remote execution, which UEFN doesn't allow. | Not applicable to UEFN. |

## Epic templates (inside UEFN, New Project)
- **Greyboxing 101**: quickest base for blocking out drill lanes and the hub. Recommended start.
- **Speedway Race with Verse Persistence**: reference for persistable player data and leaderboards
  (our `Progress.verse` follows the same `weak_map(player, ...)` pattern).
- **Gunfight**: reference for the gunplay range thread.
- No Epic template covers build practice, edit courses or aim training directly.

## Verse code libraries
| Repo | License | Verdict |
|---|---|---|
| uefncentral/uefn-verse-examples | MIT | Snippet reference (claims compiled against the API digest, 1 star). Copy patterns, not files. |
| nochbot/uefn-verse-toolkit | MIT | Mostly planned structure, little code yet. Skip. |
| IslandArchitekt/UEFN-Verse-Library, MadsMGrin/Verse, NeurealUEFN/Verse | unclear / none | No clear license or small. Don't copy. |

Nothing open source does build/edit drill grading, so that part is ours.

## Links
- Epic: [UEFN MCP docs](https://dev.epicgames.com/documentation/fortnite/uefn-mcp?lang=en-US),
  [announcement](https://www.fortnite.com/news/unreal-mcp-is-now-available-in-uefn),
  [starter templates](https://dev.epicgames.com/documentation/en-us/fortnite/unreal-editor-for-fortnite-starter-templates),
  [fort_character API](https://dev.epicgames.com/documentation/en-us/fortnite/verse-api/fortnitedotcom/characters/fort_character)
- Codex MCP config: [learn.chatgpt.com/docs/extend/mcp](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- Repos: [uefn-claude-automation](https://github.com/ViggoJonssonF/uefn-claude-automation),
  [KirChuvakov/uefn-mcp-server](https://github.com/KirChuvakov/uefn-mcp-server),
  [UEFN-TOOLBELT](https://github.com/undergroundrap/UEFN-TOOLBELT),
  [uefn-verse-examples](https://github.com/uefncentral/uefn-verse-examples)
