# Phase 0: P2P Architecture Research

**Duration:** Weeks 9-11 (AFTER Phase 7)
**Priority:** HIGH
**Based on:** [VISION.md](../docs/VISION.md) Phase 2: Global Decentralized System
**Status:** BLOCKED - Waiting for Phase 7 to complete

---

## Overview

**Objective:** Implement P2P synchronization for legal documents by building concrete implementations of the DocumentSync interface defined in Phase 7.

**IMPORTANT:** This phase now comes AFTER Phase 7. Phase 7 defines the DocumentSync abstract interface; Phase 0 implements it using specific P2P technologies.

### Why Phase 0 Comes After Phase 7

**Before (Wrong Approach):**
- Research P2P technologies with abstract requirements
- Try to design interfaces in vacuum
- Months before we know if the research is valuable

**After (Correct Approach):**
- Phase 7 defines DocumentSync ABC (concrete requirements)
- Phase 0 implements DocumentSync with specific P2P technologies
- We can test which implementation works best for our actual data volumes

### The Real Problem We're Solving

**Current User Experience:**
- Every Law7 user must:
  1. Install Docker
  2. Start 3 containers (PostgreSQL, Qdrant, Redis)
  3. Parse 157,730 Russian documents (takes hours)
  4. Run daily sync to fetch + parse new documents
- **Every user does this independently** - massive duplication of effort

**Solution:** Distributed sync where one person's parsed work benefits everyone.

---

## What Phase 7 Defines (Prerequisites)

Before starting Phase 0, Phase 7 will have defined:

### 1. DocumentSync Interface

```python
# scripts/country_modules/base/sync.py
class DocumentSync(ABC):
    """
    Abstract interface for document synchronization.

    Implementations:
    - PostgreSQLSync (current, local-only)
    - IPFSSync (IPFS-based P2P, Phase 0 PoC)
    - DPCSync (D-PC Messenger-based, Phase 0 PoC)
    """

    @abstractmethod
    async def publish_manifest(self, manifest: DocumentManifest) -> None:
        """Publish document manifest to network"""
        pass

    @abstractmethod
    async def get_manifest(self, country_id: str) -> DocumentManifest:
        """Get current manifest for country"""
        pass

    @abstractmethod
    async def publish_document(self, country_id: str, doc_id: str,
                               content: bytes, metadata: Dict[str, Any]) -> str:
        """Publish document, return content hash"""
        pass

    @abstractmethod
    async def get_document(self, country_id: str, doc_id: str) -> bytes:
        """Get document content by ID"""
        pass

    @abstractmethod
    async def subscribe_to_updates(self, country_id: str,
                                   callback: Callable[[List[str]], None]) -> None:
        """Subscribe to document updates for country"""
        pass
```

### 2. Actual Data Requirements

From Phase 7's Russia scraper:
- Document count: 157,730 documents
- Daily updates: X new documents per day (measured in Phase 7)
- Update size: Y MB per day (measured in Phase 7)
- Full dataset: Z GB (measured in Phase 7)

### 3. User Requirements

From user feedback:
- Which countries are most requested?
- How often do users sync?
- What's the acceptable sync time?
- What's the acceptable bandwidth usage?

---

## Technology Research Areas

### 1. IPFS + libp2p

| Aspect | Details |
|--------|---------|
| **Content-addressed storage** | Documents stored by hash, verifiable by anyone |
| **IPNS** | Mutable pointers for "latest version" manifests |
| **Pubsub** | Gossip protocol for change notifications |
| **IPLD** | For linking related documents (amendments, citations) |
| **Pros** | Battle-tested, large ecosystem, matches VISION.md |
| **Cons** | Complexity, requires IPFS daemon or gateway |
| **Resources** | https://docs.ipfs.io/, https://libp2p.io/ |
| **Local Repo** | `C:\Users\mike\Documents\dpc-messenger` |

### 2. D-PC Messenger (Existing Implementation)

| Aspect | Details |
|--------|---------|
| **DPTP Protocol** | D-PC Transfer Protocol for encrypted P2P messaging |
| **6-Tier Connection Fallback** | IPv6 → IPv4 → WebRTC → UDP Hole Punch → Relay → Gossip |
| **DHT-based Discovery** | Kademlia DHT for decentralized peer discovery |
| **Hub-Optional Architecture** | Works with or without central signaling server |
| **Gossip Protocol** | Multi-hop epidemic routing (fanout=3), AES-GCM+RSA-OAEP |
| **File Transfer** | 64KB chunks, SHA256 verification |
| **Knowledge Commits** | Git-like versioning system |
| **Pros** | Production-ready, local code available, battle-tested |
| **Cons** | Designed for messaging, adaptation needed for docs |
| **Local Repo** | `C:\Users\mike\Documents\dpc-messenger` |

**Key Files to Study:**
- `dpc-client/core/dpc_client_core/managers/gossip_manager.py` - Epidemic gossip
- `dpc-client/core/dpc_client_core/managers/relay_manager.py` - Volunteer relay
- `dpc-client/core/dpc_client_core/managers/hole_punch_manager.py` - UDP hole punch
- `dpc-client/core/dpc_client_core/connection_strategies/` - 6-tier strategies
- `dpc-client/core/dpc_client_core/transports/gossip_connection.py` - Gossip transport
- `dpc-client/core/dpc_client_core/consensus_manager.py` - Multi-party voting
- `docs/KNOWLEDGE_ARCHITECTURE.md` - Knowledge commit system
- `CLAUDE.md` - Complete architecture documentation

### 3. Simpler Alternatives

| Technology | Description |
|------------|-------------|
| **Git-based** | Use git as transport (legal documents as repo) |
| **Central server** | Simple HTTP server with file downloads |
| **GitHub Releases** | Publish data as releases for each country |

---

## PoC Requirements

### Each PoC Must Implement DocumentSync

```python
# scripts/research/pocs/ipfs_sync.py
from country_modules.base.sync import DocumentSync

class IPFSSync(DocumentSync):
    """IPFS implementation of DocumentSync"""

    def __init__(self):
        self.client = ipfshttpclient.connect('/dns/localhost/tcp/5001/http')

    async def publish_manifest(self, manifest: DocumentManifest) -> None:
        """Publish manifest to IPFS, update IPNS"""
        manifest_dict = {
            'country_id': manifest.country_id,
            'documents': manifest.documents,
            'last_updated': manifest.last_updated
        }
        manifest_hash = await self._ipfs.add_json(manifest_dict)
        await self._ipfs.name.publish(f"/law7/{manifest.country_id}", manifest_hash)

    async def get_manifest(self, country_id: str) -> DocumentManifest:
        """Resolve IPNS, get manifest"""
        ipns_name = f"/law7/{country_id}"
        manifest_hash = await self._ipfs.name.resolve(ipns_name)
        manifest_dict = await self._ipfs.get_json(manifest_hash)
        return DocumentManifest.from_dict(manifest_dict)

    async def publish_document(self, country_id: str, doc_id: str,
                               content: bytes, metadata: Dict[str, Any]) -> str:
        """Publish document to IPFS"""
        content_hash = await self._ipfs.add_bytes(content)
        # TODO: Store metadata with document
        return content_hash

    async def get_document(self, country_id: str, doc_id: str) -> bytes:
        """Get document by content hash"""
        # TODO: Resolve doc_id to content hash via manifest
        content = await self._ipfs.get_bytes(doc_id)
        return content

    async def subscribe_to_updates(self, country_id: str,
                                   callback: Callable[[List[str]], None]) -> None:
        """Subscribe to IPFS pubsub for country"""
        topic = f"law7-updates-{country_id}"
        # TODO: Implement IPFS pubsub subscription
        pass
```

### Benchmark Requirements

```python
# scripts/research/benchmarks/compare_sync.py

async def benchmark_publish_speed(sync_impl: DocumentSync, manifest: DocumentManifest):
    """Measure time to publish manifest"""
    start = time.time()
    await sync_impl.publish_manifest(manifest)
    return time.time() - start

async def benchmark_get_speed(sync_impl: DocumentSync, country_id: str):
    """Measure time to retrieve manifest"""
    start = time.time()
    manifest = await sync_impl.get_manifest(country_id)
    return time.time() - start

async def benchmark_bandwidth(sync_impl: DocumentSync, documents: List[bytes]):
    """Measure bandwidth usage for publishing documents"""
    # Measure bytes sent/received
    pass
```

---

## Deliverables

### Documents to Create

| Document | Description |
|----------|-------------|
| `docs/research/P2P_RESEARCH.md` | Technology comparison against DocumentSync requirements |
| `docs/research/P2P_POC_RESULTS.md` | PoC results and benchmarking metrics |
| `docs/research/P2P_ARCHITECTURE.md` | Recommended P2P architecture for Law7 |
| `docs/research/PHASE7_P2P_GUIDANCE.md` | Which P2P tech to use and why |

### Code Artifacts

| Artifact | Description |
|----------|-------------|
| `scripts/research/pocs/ipfs_sync.py` | IPFS implementation of DocumentSync |
| `scripts/research/pocs/dpc_sync.py` | D-PC implementation of DocumentSync |
| `scripts/research/benchmarks/compare_sync.py` | Benchmark script for comparing implementations |

---

## Evaluation Criteria

For each implementation, evaluate against actual requirements from Phase 7:

| Criterion | Weight | How to Measure |
|-----------|--------|---------------|
| **Manifest publish time** | HIGH | Benchmark: time to publish 157K document list |
| **Document publish time** | HIGH | Benchmark: time to publish 1MB document |
| **Get time** | HIGH | Benchmark: time to retrieve manifest and documents |
| **Bandwidth efficiency** | HIGH | Measure bytes transferred for daily sync |
| **Offline support** | HIGH | Can queries work without network? |
| **Bootstrap complexity** | MEDIUM | How easy for new user to get initial dataset? |
| **Storage overhead** | MEDIUM | Additional storage beyond PostgreSQL? |
| **Setup complexity** | MEDIUM | Does user need to run additional services? |

---

## Timeline

**Week 9:** Implement IPFS PoC
- Install and configure IPFS
- Implement IPFSSync class
- Test with sample data

**Week 10:** Implement D-PC PoC
- Study D-PC Messenger code
- Implement DPCSync class
- Test with sample data

**Week 11:** Benchmarking and Recommendation
- Run benchmarks on both implementations
- Compare against PostgreSQLSync baseline
- Write recommendation document

---

## Related Phases

- **Blocked by:** [Phase 7: Project Structure Refactoring](./PHASE7_STRUCTURE_REFACTORING.md) - MUST complete first
- **Enables:** [Phase 4: Regional Legislation](./PHASE4_REGIONAL.md) - Provides sync for multi-country

---

**Status:** BLOCKED - Waiting for Phase 7
**Owner:** TBD
**Blocked by:** Phase 7 (DocumentSync interface definition)
**Blocking:** Phase 4 (multi-country sync implementation)
