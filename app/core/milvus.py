from typing import Any, Dict, List, Optional

from pymilvus import MilvusClient, MilvusException, DataType

from app.config.config import settings


class MilvusManager:
    def __init__(self):
        self._client: Optional[MilvusClient] = None

    def connect(self) -> None:
        if self._client is not None:
            return
        uri = f"http://{settings.milvus_host}:{settings.milvus_port}"
        print(f"[Milvus] 连接: {uri}")
        try:
            self._client = MilvusClient(uri=uri, timeout=10)
            print(f"[Milvus] 连接成功 | collections: {self.list_collections()}")
        except MilvusException as e:
            self._client = None
            print(f"[Milvus] 连接失败: {e}")
            raise

    def close(self) -> None:
        if self._client is None:
            return
        self._client.close()
        self._client = None

    def is_alive(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.list_collections()
            return True
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    def list_collections(self) -> List[str]:
        if self._client is None:
            return []
        try:
            return self._client.list_collections()
        except Exception:
            return []

    def has_collection(self, name: Optional[str] = None) -> bool:
        if self._client is None:
            return False
        col = name or settings.milvus_collection
        try:
            return col in self._client.list_collections()
        except Exception:
            return False

    def create_collection(
        self,
        name: Optional[str] = None,
        dim: Optional[int] = None,
        drop_existing: bool = False,
    ) -> None:
        col = name or settings.milvus_collection
        dim = dim or settings.dashscope_embedding_dim

        if self.has_collection(col):
            if drop_existing:
                self.drop_collection(col)
            else:
                print(f"[Milvus] collection 已存在: {col}")
                return

        schema = MilvusClient.create_schema(
            auto_id=True,
            enable_dynamic_field=False,
        )
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
        schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=dim)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)
        schema.add_field(field_name="source", datatype=DataType.VARCHAR, max_length=512)
        schema.add_field(field_name="chapter", datatype=DataType.VARCHAR, max_length=512)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            metric_type="COSINE",
            index_type="HNSW",
            params={"M": 8, "efConstruction": 64},
        )

        self._client.create_collection(
            collection_name=col,
            schema=schema,
            index_params=index_params,
        )
        print(f"[Milvus] collection 创建成功: {col} (dim={dim})")

    def drop_collection(self, name: Optional[str] = None) -> None:
        col = name or settings.milvus_collection
        self._client.drop_collection(col)
        print(f"[Milvus] 已删除 collection: {col}")

    def insert(
        self,
        texts: List[str],
        vectors: List[List[float]],
        sources: List[str],
        chapters: List[str],
    ) -> None:
        if self._client is None:
            raise RuntimeError("Milvus 未连接")
        data = []
        for i in range(len(texts)):
            data.append({
                "vector": vectors[i],
                "content": texts[i],
                "source": sources[i],
                "chapter": chapters[i],
            })
        self._client.insert(collection_name=settings.milvus_collection, data=data)

    def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        output_fields: Optional[List[str]] = None,
        expr: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if self._client is None:
            return []
        if output_fields is None:
            output_fields = ["content", "source", "chapter"]

        results = self._client.search(
            collection_name=settings.milvus_collection,
            data=[query_vector],
            anns_field="vector",
            limit=top_k,
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
            filter=expr,
            output_fields=output_fields,
        )

        rows = []
        for hits in results:
            for hit in hits:
                entity = hit.get("entity", {})
                row = {"id": hit["id"], "distance": hit["distance"]}
                for f in output_fields:
                    row[f] = entity.get(f)
                rows.append(row)
        return rows

    def get_all_chunks(self, limit: int = 16384) -> List[Dict[str, Any]]:
        if self._client is None or not self.has_collection():
            return []
        return self._client.query(
            collection_name=settings.milvus_collection,
            filter="id >= 0",
            output_fields=["content", "source", "chapter"],
            limit=limit,
        )

    def delete_by_source(self, source: str) -> None:
        if self._client is None:
            return
        self._client.delete(
            collection_name=settings.milvus_collection,
            filter=f'source == "{source}"',
        )


milvus_manager = MilvusManager()
