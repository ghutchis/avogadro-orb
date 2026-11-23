# avogadro-orb

Energy and gradient models from Orbital Materials' Orb family, via the
[orb-models](https://github.com/orbital-materials/orb-models) package.
Conservative (energy-derived force) models only, run in float64 on CUDA if
available, otherwise on CPU (never MPS).

## Models

| Name | Checkpoint | Systems | Elements |
| --- | --- | --- | --- |
| OrbMol-v2 | `orbmol-v2-teqabfhg-20260523` | molecules and periodic; charged and open-shell | 1-86, 88-99 |
| Orb-v3 (OMat24) | `orb-v3-conservative-inf-omat-20250404` | periodic materials; neutral, closed shell only | 1-88 |

- **OrbMol-v2**: trained on OMol25 and OPoly26 (wB97M-V/def2-TZVPD) with
  learnable electrostatics (Coulomb sum for molecules, PME for periodic cells).
  Avogadro's total charge and spin multiplicity are passed to the model.
- **Orb-v3**: trained on OMat24 (PBE/PBE+U). It has no charge or spin input, so
  Avogadro hides it for ions and radicals.

Element lists come from the model code, not the papers: the reference-energy
tables in the loaded checkpoints are fitted for exactly those atomic numbers
(OrbMol-v2 has no entry for Fr and none above Es; Orb-v3 shares one constant
for every element above Ra, i.e. untrained). The network embeddings themselves
accept up to Z = 117, so heavier elements run but are meaningless.

## Citations

- Rhodes et al., "Orb-v3: atomistic simulation at scale", arXiv:2504.06231.
- Orbital Materials, OrbMol / OrbMol-v2 (see the orb-models README and
  MODELS.md) and the OMol25 and OMat24 datasets.

## Licenses

The orb-models code and the released model weights are Apache-2.0. This plugin
is BSD-3-Clause. (The OMol25 / OMat24 / OPoly26 datasets carry their own
licenses; see their publications.)

## Platforms

Locks for osx-arm64 and linux-64. Only osx-arm64 has been tested; linux-64
(CPU or CUDA) is untested. Upstream supports macOS and Linux; Windows is "not
guaranteed", so it is not listed. Python is pinned to 3.12 because orb-models
requires `dm-tree==0.1.8`, which has no wheels for newer Pythons.

The first Warp kernel compilation happens during `pixi run setup`, which also
downloads both checkpoints (about 100 MB each). Cold start of the model
process afterward is roughly 10 s on an Apple M-series CPU.

## Development

```bash
pixi install
pixi run setup
pixi run test
```

Avogadro starts the model once, as
`pixi run avogadro-orb OrbMol-v2 --protocol binary-v1`, sends
one line of bootstrap JSON, and then exchanges binary frames with it for as
long as the model stays selected. The loop ends when Avogadro closes stdin.

That single long-running process is the thing to keep in mind while editing
`src/avogadro_orb/orbmol_v2.py`:

- **Nothing may print to stdout.** stdout is the protocol. A `print()` left in
  for debugging, or a dependency that greets you on import, breaks the stream.
  Write to `sys.stderr` instead; `--debug` is there for exactly this.
- **Return the gradient, not the force.** Avogadro wants dE/dx in
  kJ/mol/Angstrom. ASE and most ML potentials give forces, which are its
  negative.
- **Units are kJ/mol and Angstrom.** Hartree, eV and kcal/mol all need
  converting.
- **Answer every request.** On failure send `request.send_error(...)` rather
  than raising, so the process survives to answer the next one.

`pixi run test` drives the real protocol against the real entry point in a
subprocess. It checks the analytic gradient against finite differences of the
energy, which is what catches a sign or unit error before Avogadro does, and it
asserts that stdout carries protocol frames and nothing else, which catches the
stray print. Note that a `print()` can pass a casual manual test and still be a
bug: Python block-buffers text stdout into a pipe, so the output often appears
harmlessly at exit right up until some flush lands it between two frames.

### Replacing the model

Only the top half of `src/avogadro_orb/orbmol_v2.py` is meant to
change:

1. `_prepare()` — build the calculator and anything else that survives across
   requests.
2. `_energy()` and `_energy_and_gradient()` — the calculation itself.
3. Update `support.elements` and the other `support.*` keys in
   `pyproject.toml` to match what the new model actually handles. Avogadro
   treats them as promises and will offer the model wherever they say it works.

### Adding a model

1. Add a `[[tool.avogadro.energy-models]]` block to `pyproject.toml` with a new
   `identifier`.
2. Add a matching `case` to `src/avogadro_orb/__init__.py`.
3. Write it in its own module, importing it inside that `case` so its
   dependencies load only when it is used.

## Installing

In Avogadro: **Extensions → Plugin Manager → Install from directory**, and
choose this folder.

## Suggestions

Please file suggestions and bugs at
<https://github.com/ghutchis/avogadro-orb/issues>.
