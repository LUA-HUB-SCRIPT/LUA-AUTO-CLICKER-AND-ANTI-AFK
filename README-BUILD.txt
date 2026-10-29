LUAHUB AFK CONTROL CENTER — GitHub Actions EXE build

Upload the contents of this folder into the ROOT of your GitHub repository, keeping
the .github/workflows/build-windows-exe.yml path intact.

Then:
1. Commit/push to the main or master branch, OR open Actions and manually run
   "Build LUAHUB AFK Control EXE".
2. Open the successful workflow run.
3. Download the artifact named LUAHUB-AFK-Control-EXE.
4. Extract it to get LUAHUB-AFK-Control.exe.

The EXE is built on a GitHub Windows runner; it is not included in this source ZIP.
This app provides desktop keep-awake and ordinary click automation where permitted.
It does not bypass game AFK detection or anti-cheat. F12 is an emergency stop;
PyAutoGUI failsafe is enabled (move the pointer to the top-left corner).
