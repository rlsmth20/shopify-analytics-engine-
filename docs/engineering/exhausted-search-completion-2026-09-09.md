# Exhausted search completion

A real discovery task read a resolved merchant question and retained relevant
community evidence, correctly choosing not to add another vendor pitch. Its
result had no successor and no mission stop. The executor rejected it, then
attempted the same research again until the task research budget was exhausted.

The acceptance validator now permits a discovery result to finish without a
successor when it has retained source observations, a nonnegative integer result
count, zero qualified results and nonempty reason codes. This does not grant
permission to send or declare the mission complete. Existing search history and
hypothesis retirement retain the outcome; the persistent planner owns next work.

All 16 executor tests passed, including exhausted search to autonomous planning,
missing-evidence rejection, positive-result rejection without continuation,
reply priority, leases, and uncertain forms leaving other acquisition available.

This function runs in the existing local executor. No Railway or frontend
deployment is needed. Recover the original retained result with its observation
time and fault reference; preserve attempt history. Do not repeat the research,
seed discovery work, reset reservations, or send messages during recovery.
