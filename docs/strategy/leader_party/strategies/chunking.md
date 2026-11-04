# Experimental chunk geometry

`World::chunk` uses ceil(width/15) by ceil(height/15) balanced rectangular partitions. A 100x100 map uses 7x7=49 chunks, fitting six bits. ID 63 means absent. The inverse center function uses the same integer boundaries.

A chunk is a hint, never an exact objective. Experimental visible leader guidance joins a camp only when the local observation resolves exactly one candidate in the chunk near that leader. Remote rally inspection is not implemented and coordination is disabled in the release. Camp IDs and task state remain local.
