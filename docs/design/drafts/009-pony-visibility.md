# 009 / Keeping a pony above the ground

**Field study draft — SkyStack Builder.** A renderer migration in progress. This draft is outside the published archive, feed and sitemap.

Turn an island around and a familiar place can become unfamiliar for the wrong reason. A pony that stood beside a block is suddenly buried in it. The world has not moved. The view has.

That is more than a drawing blemish. A builder asks the player to understand where things are, choose a place and trust the result. If a character slips beneath the ground when the camera turns, the picture stops being a dependable account of the world.

## One view needs several kinds of depth

SkyStack's Direct3D migration keeps the game's shared camera and projection. That preserves a common language for looking and picking. It does not automatically tell every painted detail where it belongs in three dimensions.

A block face can carry a depth plane. Its outline needs the depths of its actual endpoints. A character's artwork has another complication: some of the image extends below the point where its feet meet the ground. Treating every part as an ordinary upright sheet can let the supporting block cut off the feet.

The experimental renderer recognises a support surface and a receiver block. It also tries to keep later terrain drawing beneath a nearer actor without making the actor immune to genuinely raised foreground blocks. Those are separate obligations. Fixing one by ignoring the other would exchange buried feet for a pony visible through a wall.

## An incomplete picture can answer a useful question

One native contact fixture places a pony among neighbouring grass blocks, at 45 degrees of yaw, 62 degrees of pitch and 0.85 zoom. The complete experimental render retains 192 of 201 high-coverage body samples and 13 of 20 contact samples. It still fails the full-contact assertion.

A deliberately incomplete diagnostic draws only later terrain packets with known depth metadata. That version retains all 201 body samples and all 20 contact samples.

The better-looking diagnostic is not the repaired game. It has removed details from the picture. What it provides is a narrower question: which of the remaining authored packets paint over those pixels, and what geometry should describe their depth?

Adding metadata to several side-decoration families has not yet recovered the complete fixture. That result matters too. A plausible place to add code is not necessarily the place responsible for the fault.

## Keep the details and repair their account of place

The next observation should follow the actual packets crossing the missing pixels. A small bevel or patch of soil deserves the same care as the large block beneath it. Its world endpoints belong beside the geometry that creates it, not in a later guess based on screen position.

After that correction, the whole picture must pass again. Turn the camera. Put a raised block in front. Test a ramp. Keep the same picking and placement behaviour. Then measure the frame time on the laptop where the game will be played.

The island's atmosphere depends on these small agreements. A pony should belong to the ground without disappearing into it.

## Source and limits

Pinned implementation: [SkyStack Builder at d68bdc6](https://github.com/digablesolutions/sky-stack-builder/tree/d68bdc6e182548e62f9c093470be327b4bd6fb93).

- [Renderer status and native-test receipts](https://github.com/digablesolutions/sky-stack-builder/blob/d68bdc6e182548e62f9c093470be327b4bd6fb93/docs/gpu-parity-status.md) records the complete and classified-only comparisons. The named local receipt files are not bundled with this editorial draft.
- [Contact fixture](https://github.com/digablesolutions/sky-stack-builder/blob/d68bdc6e182548e62f9c093470be327b4bd6fb93/tests/SkyStackBuilder.Tests/main.cpp), [packet generation](https://github.com/digablesolutions/sky-stack-builder/blob/d68bdc6e182548e62f9c093470be327b4bd6fb93/src/render/game_app_render.cpp), and [GPU composition](https://github.com/digablesolutions/sky-stack-builder/blob/d68bdc6e182548e62f9c093470be327b4bd6fb93/src/render/direct3d_backend.cpp) define the experiment.

The complete contact test was run and still fails. These counts describe one fixture, not all actors or camera angles. The underlay path remains opt-in; this note does not establish full parity, frame-time improvement or player comprehension. There are no gameplay screenshots in this draft.

Related draft: [What one pixel can prove](010-pixel-evidence.md).
