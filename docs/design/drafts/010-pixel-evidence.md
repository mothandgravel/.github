# 010 / What one pixel can prove

**Field study draft — SkyStack Builder.** Native rendering experiments and their limits. This draft is outside the published archive, feed and sitemap.

![Three translucent sage, blue and rose sheets overlap on warm paper beneath a brass magnifying lens.](renderer-studies-assets/010-cover-1600.webp)

*Looking closely at a small disagreement. AI-generated editorial metaphor, not measured colour swatches or a rendering test capture.*

Two pictures can look almost the same and disagree at thousands of pixels. Two tests can both turn green and disagree about whether the game is ready.

The useful question is not simply whether there is a difference. It is what the difference measures.

## Rounding has a place in the picture

SkyStack's experimental renderer saves painted content into a transparent GPU layer, then combines it with the scene later. That can preserve an intended relationship without moving all the terrain drawing after the actors.

There is a small cost to changing where painting happens. An eight-bit colour target rounds the result after drawing. Three translucent packets drawn one after another onto the scene do not necessarily produce the same bytes as the same packets first combined into a transparent layer and then placed over the scene.

A native control removes the game from the question: no terrain, actor or depth test, just three overlapping translucent rectangles. On a pure-green background, the chosen example matches exactly. On an RGB background of 37, 113, 197, it differs at 4,000 pixels. The largest difference is one level in a colour channel.

The first comparison did not prove rounding irrelevant. The second did not prove every visible fault was rounding. Together they show why a single convenient background is a weak witness.

## A small explanation must not swallow a large failure

![Sequential drawing rounds three blends onto the scene; grouped drawing rounds three blends onto a transparent target, then rounds a final blend onto the scene.](renderer-studies-assets/010-rounding-boundaries.png)

*A conceptual blend sequence. Both paths round intermediate draws; the group changes their destination and adds a final composition. This is not a measured pixel image.*

The larger party-and-actor comparisons contain differences reaching 122 channel levels in an earlier recorded run. A one-level control cannot explain those away.

Other controls separate actor-only changes from party changes, missing coverage from added coverage, and supporting terrain from foreground terrain. Each removes one possible explanation. None is a substitute for the whole scene.

Even an exact match can have a narrow meaning. A backend proof can preserve a half-opacity actor beneath a later terrain rectangle exactly. That says something valuable about the composition rule. It does not say the gameplay renderer has assigned every terrain detail the right depth, or that several overlapping actors will work the same way.

## Keep the test attached to its question

A useful result carries its conditions with it. Which scene? Which camera? Which renderer mode? Which reference? Did the process finish, or did someone merely stop watching it?

Those details need not become a wall of numbers for the player. They belong in the workbench record so that a calm public claim has something solid underneath it.

The next comparison should preserve the original full-scene assertion while separating any intended correction from accidental colour changes. A test that removes troublesome geometry may explain a failure. It cannot certify the geometry it removed.

One pixel can prove a particular disagreement. Read carefully, it can also keep a team from claiming more than it knows.

## Source and limits

- [Native layer controls](https://github.com/digablesolutions/sky-stack-builder/blob/d68bdc6e182548e62f9c093470be327b4bd6fb93/tests/SkyStackBuilder.Tests/main.cpp) include `TestPainterVisibilityLayer` and the party ownership fixtures.
- [The recorded findings](https://github.com/digablesolutions/sky-stack-builder/blob/d68bdc6e182548e62f9c093470be327b4bd6fb93/docs/gpu-parity-status.md) distinguish the exact fractional-foreground proof, the group-rounding counterexample and failing full-scene comparisons.
- [The backend](https://github.com/digablesolutions/sky-stack-builder/blob/d68bdc6e182548e62f9c093470be327b4bd6fb93/src/render/direct3d_backend.cpp) contains the corresponding GPU paths.

The figures are fixture results recorded in the renderer work, not perceptual tolerances established with players. This editorial draft adds no new benchmark and makes no claim that a one-level difference is always harmless. Full renderer acceptance remains incomplete.

Related draft: [Keeping a pony above the ground](009-pony-visibility.md).
