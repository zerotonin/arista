File formats
============

.. note::

   Full format reference lands in sprint 10. See
   ``Preprocessing Pipeline.md`` in the project notebook for the current
   working description.

Inputs
------

* **Fiji ΔF/F₀ export** — 2-column CSV/TXT, header ``X,Y``: frame
  index and ΔF/F₀ per frame.
* **MATLAB sensor record** — ``.mat`` with a single ``data`` matrix of
  ``[epoch_time, frame_idx, sensor_T, target_T, drive_T]`` rows.

Outputs
-------

* **Aligned + drift-corrected CSV** — columns
  ``frames, temperatureDeg, targetTempDeg, deltaFbyF, time_sec, dFbF_driftCorr``;
  the drift method is encoded in the filename (``…_driftCorr-<method>_…``).
