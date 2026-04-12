from app.services.rag_service import get_rag_service

rag = get_rag_service()
print("可用:", rag.is_available)

if rag.is_available:
    result = rag.search("小麦储存的安全温度标准")
    for r in result["results"]:
        print(f"[相似度 {r['relevance_score']}] {r['title']}")
        print(r["content"][:150])
        print()
else:
    print("RAG 服务不可用")
