# dexsuiteorg.github.io

Project page for **DexSuite: An All-in-One Framework for Dexterous Manipulation Across Arms, Hands, and Tasks**
(static GitHub Pages site, nerfies/Bulma theme).

The page is generated, not edited by hand:

1. `python3 tools/build_site.py` writes `index.html` from the paper's sources (Overleaf clone at
   `/efs/projects/fudi/test_stuff/paper_ol`): title, abstract, framework, teleoperation, tactile, dataset and benchmark
   text, Table II and the numbers in the key-facts strip. Re-run it after a paper edit.
2. `.venv-dexsuite/bin/python tools/build_data_viewer.py` builds the data viewer assets in `static/data_viewer/`:
   three episodes for each task, embodiment and collection tier of the dataset, cut from the LeRobot v3 videos (front and
   wrist cameras side by side, H.264) with the tool center point trajectory. Human, scripted and machine-generated sets are
   read from huggingface.co/dexsuite, the two Sharpa sets from the local collection until they are uploaded.

Assets:
- `static/images/paper/`: the paper's figures (overview, teleoperation devices, tactile, dataset wheel, benchmark tasks,
  stage outcomes), converted from `paper_ol/assets` with `pdftoppm -r 220` (wheel and stages at 440 dpi).
- `static/videos/tasks/`: carousel clips, 1280x720. Allegro and UMI clips are rollouts of the released policies from a
  fixed camera; the Sharpa clips are the scripted experts filmed with the `picture` camera.
- `static/css/site.css`, `static/js/site.js`, `static/js/data_viewer.js`: additions on top of the original theme files.

Local preview: `python3 -m http.server 8770 --bind 127.0.0.1` in this folder, then open http://localhost:8770.
