# Result figures (astroplot contract, ~/astro/docs/PLOT_BRIEF.md)

Empty until milestone 5: the 3-5 key figures are proposed to the user first (fraction of double bars vs M*, length-ratio and
misalignment distributions, Omega_in/Omega_out, ...). Each will be `plots/<topic>.py` with `make()` and `main()`, written with
`save(fig, name, "bars", runs=[...])`; `astroplot-check plots/*.py` must print `ok`.
Per-galaxy diagnostic figures are not here: step 04 writes them to `$ASTRO_RUNDIR/figures/`.
