# Modules API Reference

An energy model is assembled from three modules, each a
[`NewsegsModule`][newsegsmodelframework.core.newsegsmodule.NewsegsModule]:

* **Grid** - the wider electricity grid;
* **Generation** - on-site generation (wind, PV...);
* **CS** - on-site consumption and storage.

::: newsegsmodelframework.newsegsgrid
    options:
        show_submodules: true

::: newsegsmodelframework.newsegsgeneration
    options:
        show_submodules: true

::: newsegsmodelframework.newsegscs
    options:
        show_submodules: true
