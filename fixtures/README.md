# Recorded provider fixtures

Every `LocalModelProvider` call writes its `(request, response)` pair here, keyed
by a hash of the diagnosis and the source it saw.

This exists so that a published number can be reproduced by someone else,
offline, at zero cost, and so that a recorded demo replays byte-for-byte. Keep
them in version control — they are how a reader checks the results table without
credentials.

`LocalModelProvider(replay_only=True)` refuses to synthesize a response when no
fixture matches, which is how you prove a result was replayed rather than
regenerated.
