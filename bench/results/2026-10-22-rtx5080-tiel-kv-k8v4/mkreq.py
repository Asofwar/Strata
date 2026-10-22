# Request files for the engine's --serve stdin (GEN <max_new> <ids>).
# speed: warm 2K, then 130K x3 and 200K x3, each from scratch (token 0 changed per request so the conversation cache
# reuses nothing); 130K first so the elastic K/V grows 130K -> 200K once, as on the live server.
# kl: the prefill-200k session's teacher-forced file (64K/130K/200K, last 512 tokens through the verify windows).
import os, shutil
S = os.path.dirname(os.path.abspath(__file__))
P9 = r"C:\Users\Admin\AppData\Local\Temp\claude\E--Projects-Strata-fork--claude-worktrees-prefill-200k-215f08\9f9c99df-e89e-4d92-af31-f8bfc5ea149d\scratchpad"
P3 = r"C:\Users\Admin\AppData\Local\Temp\claude\E--Projects-Strata-fork--claude-worktrees-mystifying-torvalds-f3a708\38cbbe6e-d07a-4442-b747-b2609bfabf19\scratchpad"
a = open(os.path.join(P9, "t130k.txt")).read().strip().split(",")
b = open(os.path.join(P9, "t200k.txt")).read().strip().split(",")
warm = open(os.path.join(P3, "seq_alt4.txt")).readline()
assert warm.startswith("GEN 192 ")
NEW = 192
lines = [warm]
for k in range(3):
    lines.append(f"GEN {NEW} {','.join([str(4000 + k)] + a[1:])}\n")
for k in range(3):
    lines.append(f"GEN {NEW} {','.join([str(5000 + k)] + b[1:])}\n")
lines.append("QUIT\n")
with open(os.path.join(S, "seq_speed.txt"), "w", encoding="utf-8", newline="\n") as f:
    f.writelines(lines)
shutil.copyfile(os.path.join(P9, "seq_kl.txt"), os.path.join(S, "seq_kl.txt"))
print("speed", len(a), len(b), "kl copied")
