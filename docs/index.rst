arista
======

Calcium-imaging corpus and analysis package for *Drosophila melanogaster*
arista thermosensory neurons.

The package consolidates calcium-imaging recordings across four students
(Robert Kossen, Niko, Laurin Büld, Alexander Busch) into a single SQLite
database, ships a headless preprocessing CLI that reproduces the original
``pytci`` pipeline on user-supplied raw data, and rebuilds the publication
figures supporting the role of NompC in thermosensation.

.. note::

   This documentation is the **alpha** scaffold for the v0.1.0 release.
   User guide, CLI reference, and API pages will fill in over sprints 2-10
   of the refactor (see ``Refactor Plan.md`` in the project notebook).

Quick links
-----------

* `Source on GitHub <https://github.com/zerotonin/arista>`__
* `Robert Kossen (2019) PhD thesis
  <https://github.com/zerotonin/arista/blob/main/_legacy/README.md>`__
  — the scientific provenance for the corpus

Citation
--------

If you use this software or the bundled dataset, please cite the
``CITATION.cff`` at the repository root.

.. toctree::
   :maxdepth: 2
   :caption: User guide

   quickstart
   file_formats
   pipeline
   cli

.. toctree::
   :maxdepth: 2
   :caption: Internals

   ingest
   figures

.. toctree::
   :maxdepth: 1
   :caption: Reference

   api/modules

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
