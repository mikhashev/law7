# Phase 0: P2P Architecture Research

**Duration:** Weeks 1-3 (parallel with Phase 1)
**Priority:** HIGH - Research must inform Phase 7 adapter pattern design
**Based on:** [VISION.md](../docs/VISION.md) Phase 2: Global Decentralized System

---

## Overview

**Objective:** Research P2P/blockchain technologies for decentralized legal data synchronization, ensuring Phase 7's adapter pattern can eventually support P2P without major rewrites.

This research phase runs in parallel with Phase 1 to ensure architectural decisions are informed by future requirements.

---

## Key Questions

1. How can legal documents be synchronized across distributed nodes?
2. What technologies support:
   - Content-addressed storage (hash-based verification)
   - Delta updates and diff tracking
   - Gossip/pubsub for change notifications
   - Offline-first operation
   - Community verification and trust
3. Which technology stack best fits Law7 requirements?

---

## Technology Research Areas

### 1. IPFS + libp2p

**As mentioned in VISION.md**

| Aspect | Details |
|--------|---------|
| **Content-addressed storage** | Documents stored by hash, verifiable by anyone |
| **IPNS** | Mutable pointers for "latest version" of legal codes |
| **Pubsub** | Gossip protocol for change notifications |
| **DAG** | IPLD for linking related documents (amendments, citations) |
| **Pros** | Battle-tested, large ecosystem, matches VISION.md |
| **Cons** | Complexity, requires IPFS daemon or gateway |
| **Resources** | https://docs.ipfs.io/, https://libp2p.io/ |

### 2. DAT Protocol / Hypercore

| Aspect | Details |
|--------|---------|
| **Hypercore DAG** | Append-only logs with versioning |
| **Peer-to-peer sync** | Direct sharing between participants |
| **Sparse replication** | Download only needed data |
| **Built-in diffing** | Efficient delta updates |
| **Pros** | Simpler than IPFS, designed for datasets, good sync |
| **Cons** | Smaller ecosystem, less widely adopted |
| **Resources** | https://datprotocol.org/, https://hypercore-protocol.org/ |

### 3. ActivityPub / Fediverse

| Aspect | Details |
|--------|---------|
| **Decentralized social** | Mastodon, Lemolia use this |
| **Inbox/Outbox model** | Follow legal document updates |
| **Server-to-server federation** | Each country runs their own server |
| **Pros** | W3C standard, proven at scale, simpler concepts |
| **Cons** | Not designed for large datasets, no content addressing |
| **Resources** | https://www.w3.org/TR/activitypub/ |

### 4. D-PC Messenger (Existing Implementation)

**Repository:** https://github.com/mikhashev/dpc-messenger

| Aspect | Details |
|--------|---------|
| **DPTP Protocol** | D-PC Transfer Protocol for encrypted P2P messaging |
| **6-Tier Connection Fallback** | IPv6 → IPv4 → WebRTC → UDP Hole Punch → Relay → Gossip |
| **DHT-based Discovery** | Kademlia DHT for decentralized peer discovery |
| **Hub-Optional Architecture** | Works with or without central signaling server |
| **Gossip Protocol** | Store-and-forward for disaster resilience |
| **DTLS Encryption** | End-to-end encryption for all connection strategies |
| **Knowledge Commits** | Git-like versioning system |
| **Pros** | Production-ready, battle-tested, GPL/LGPL/AGPL licenses, active development |
| **Cons** | Designed for messaging, may need adaptation for document distribution |

**Key Files to Study:**
- `dpc-client/core/dpc_client_core/protocols/` - Protocol implementations
- `dpc-client/core/dpc_client_core/network/` - 6-tier connection orchestrator
- `dpc-client/core/dpc_client_core/dht/` - Kademlia DHT implementation
- `dpc-client/core/dpc_client_core/gossip/` - Gossip protocol
- `docs/KNOWLEDGE_ARCHITECTURE.md` - Knowledge commit system

### 5. Generic / Custom Solutions

| Technology | Description |
|------------|-------------|
| **Git-based** | Use git as the transport (legal documents as repo) |
| **Bittorrent + magnets** | Swarm-based distribution |
| **Secure Scuttlebutt** | Append-only social logs |
| **Ethereum/IPFS hybrids** | Smart contracts for verification |

---

## Evaluation Criteria

For each technology, evaluate against Law7 requirements:

| Criterion | Weight | Notes |
|-----------|--------|-------|
| Content addressing | HIGH | Hash-based verification required |
| Delta updates | HIGH | Legal documents change frequently |
| Offline-first | HIGH | Must work without central server |
| Verification trust | HIGH | Community can verify official sources |
| JavaScript/Python support | MEDIUM | Must work with our stack |
| Learning curve | MEDIUM | Affects implementation time |
| Ecosystem maturity | MEDIUM | Libraries, documentation, community |
| Bandwidth efficiency | MEDIUM | Large document sets |
| Bootstrap complexity | LOW | Easy for new participants to join |

---

## Proof-of-Concept Requirements

### PoC Scope

Build minimal PoC for top 2-3 technologies with the following requirements:

```python
# PoC Requirements (for each tech)
1. Publish sample legal document (1-5MB)
2. Retrieve document by hash
3. Publish updated version with delta
4. Verify hash matches official source
5. Subscribe to changes (pubsub/gossip)
6. Measure: bandwidth, sync time, storage overhead
```

### Sample Dataset

- 100 Russian federal laws (HTML/PDF)
- 1 complete legal code (GK RF Part 1)
- 10 amendment documents
- **Total:** ~50MB

---

## Decision Matrix

| Technology | Content Addressing | Delta Updates | Pubsub | Complexity | Recommendation |
|------------|-------------------|---------------|--------|------------|----------------|
| IPFS/libp2p | ✅ Native | Via IPLD | ✅ Native | High | ? |
| DAT/Hypercore | ✅ Native | ✅ Built-in | ⚠️ Limited | Medium | ? |
| ActivityPub | ❌ No | ❌ No | ✅ Native | Low | ? |
| D-PC Messenger | ✅ Knowledge Commits | ✅ Gossip | ✅ 6-tier | Medium | ? |
| Git-based | ✅ Via commits | ✅ Via diff | ❌ No | Low | ? |

---

## Architecture Recommendations for Phase 7

Based on research findings, provide guidance for:

1. **Adapter interface design** - Ensure it works with both centralized DB and P2P
2. **Document ID format** - Use content hashes from day 1
3. **Version tracking** - Design for eventual DAG-based amendment chains
4. **Sync abstraction** - Separate storage from synchronization

### Example: P2P-Compatible Adapter Interface

```python
# Design adapter interface to work with both backends
class CountryAdapter(ABC):
    @abstractmethod
    def fetch_document(self, doc_id: str) -> Document:
        """Works with PostgreSQL OR IPFS"""
        pass

    @abstractmethod
    def get_document_hash(self, doc_id: str) -> str:
        """Content hash - primary key in both systems"""
        pass

    @abstractmethod
    def subscribe_to_updates(self, callback: Callable):
        """Works with PostgreSQL LISTEN OR IPFS pubsub"""
        pass
```

---

## Deliverables

### Documents to Create

| Document | Description |
|----------|-------------|
| `docs/P2P_RESEARCH.md` | Detailed findings on each technology |
| `docs/P2P_POC_RESULTS.md` | Proof-of-concept results and metrics |
| `docs/P2P_ARCHITECTURE.md` | Recommended architecture for Phase 2 |
| `docs/PHASE7_P2P_GUIDANCE.md` | Design recommendations for Phase 7 |

### Code Artifacts

| Artifact | Description |
|----------|-------------|
| PoC implementations | Minimal implementations for top 2-3 technologies |
| Benchmark scripts | Performance comparison scripts |
| Sample adapter | Demonstrating P2P compatibility |

---

## Timeline

**Week 1-2:** Research and documentation
- Deep dive into IPFS/libp2p, DAT, ActivityPub, D-PC Messenger
- Document findings, pros/cons
- Identify top 2-3 candidates

**Week 3:** Proof-of-concept
- Build minimal PoC for each candidate
- Run benchmarks
- Create decision matrix

**Output:** Architecture recommendations for Phase 7

---

## Related Phases

- **Informs:** [Phase 7: Project Structure Refactoring](./PHASE7_STRUCTURE_REFACTORING.md)
- **Runs in parallel with:** [Phase 1: Foundation](./PHASE1_FOUNDATION.md)

---

**Status:** Not Started
**Owner:** TBD
**Blocked by:** None
**Blocking:** Phase 7 implementation
