
class CycleData:
    # tar2src  -> map target var to source var
    # src2tar  -> map source var to target var (!)
    # tar2loc  -> map target var to location
    # src2loc  -> map source var to location
    # loc2src  -> map location to source var
    # srcstack -> list of source vars
    # freshctr -> how many fresh locations have we made so far
    # emitted  -> list of emitted targets
    pass

def emit_moves(gen, tar2src, tar2loc, src2loc):

    # Basic idea:
    #
    #   Construct a dependency graph, with a node for each move (Ti <-
    #   Si).  Add an edge between two nodes i and j if loc[Ti] ==
    #   loc[Sj].  (If executing the node's move would overwrite the
    #   source for another move).  If there are no cycles, then a
    #   simple tree walk will suffice.  If there *ARE* cycles, however,
    #   something more is needed.
    #
    #   In a nutshell, the algorithm is to walk the tree, and whenever
    #   a backedge is detected break the cycle by creating a fresh
    #   location and remapping the source of the node so that it no
    #   longer conflicts.  So, if you are in node i, and you detect a
    #   cycle involving node j (so, Ti and Sj are the same location),
    #   then you create a fresh location Sn.  You move Sj to Sn, and
    #   remap node j so that instead of being Tj <- Sj it is Tj <- Sn.
    #   Now there is no need for the backedge, so you can continue.
    #   Whenever you have visited every edge going out from a node, all of
    #   its dependent moves have been performed, so you can emit the
    #   node's move and return.

    tarvars = tar2src.keys()
    
    data = CycleData()
    data.tar2src = tar2src
    data.src2tar = {}
    data.tar2loc = tar2loc
    data.src2loc = src2loc
    data.loc2src = {}
    data.srcstack = []
    data.freshctr = 0
    data.emitted = []

    for tar, src in tar2src.items():
        data.src2tar[src] = tar

    for src, loc in src2loc.items():
        if src in data.src2tar:
            data.loc2src[loc] = src

    for tarvar in tarvars:
        _cycle_walk(gen, tarvar, data)
            
    return data

def _cycle_walk(gen, tarvar, data):

    if tarvar in data.emitted: return

    #print "tarvar in data.tar2loc", tarvar in data.tar2loc
    tarloc = data.tar2loc[tarvar]
    #print "tarvar in data.tar2src", tarvar in data.tar2src
    srcvar = data.tar2src[tarvar]
    #print "srcvar in data.src2loc", srcvar, srcvar in data.src2loc
    srcloc = data.src2loc[srcvar]



    # if location we are about to write to is not going to be read
    # by anyone, we are safe
    if tarloc not in data.loc2src:
        gen.emit_move(tarloc, srcloc)
        data.emitted.append(tarvar)
        return

    # Find source node that conflicts with us
    #print "tarloc in data.loc2src", tarloc in data.loc2src
    conflictsrcvar = data.loc2src[tarloc]

    if conflictsrcvar not in data.srcstack:
        # No cycle on our stack yet
        data.srcstack.append(srcvar)
        #print "conflictsrcvar in data.src2tar", conflictsrcvar in data.src2tar
        _cycle_walk(gen, data.src2tar[conflictsrcvar], data)
        #print "srcvar in data.src2loc", srcvar in data.src2loc
        srcloc = data.src2loc[srcvar] # warning: may have changed, so reload
        gen.emit_move(tarloc, srcloc)
        data.emitted.append(tarvar)
        return 
    
    # Cycle detected, break it by moving the other node's source data
    # somewhere else so we can overwrite it
    freshloc = gen.create_fresh_location()
    #print "conflictsrcvar in data.src2loc", conflictsrcvar in data.src2loc
    conflictsrcloc = data.src2loc[conflictsrcvar]
    gen.emit_move(freshloc, conflictsrcloc)
    data.src2loc[conflictsrcvar] = freshloc
    gen.emit_move(tarloc, srcloc) # now safe to do our move
    data.emitted.append(tarvar)
    return
