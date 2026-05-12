Quickstart
==========

.. note::

   Full quickstart lands in sprint 10. The placeholder below documents
   the *intended* user workflow so reviewers can sanity-check the
   reproducibility track at a glance.

Install
-------

.. code-block:: bash

   pip install arista-thermosensation
   # or, from the Zenodo source bundle:
   pip install -e .

Preprocess one recording on the shipped fixtures
------------------------------------------------

.. code-block:: bash

   arista-preprocess align \\
       data/fiji/HC01.csv \\
       data/sensor/temperature_data_2021_12_20-12_40.mat \\
       -o aligned.csv

   arista-preprocess drift aligned.csv -o corrected.csv --method auto

Preprocess your own raw Ca²⁺ imaging data
-----------------------------------------

.. code-block:: bash

   arista-preprocess batch my_raw_data/ -o preprocessed/ \\
       --layout generic --method auto

Build the database and rebuild figures
--------------------------------------

.. code-block:: bash

   arista-ingest --root preprocessed/ --db arista.db
   arista-figs   --db arista.db --output figures/
