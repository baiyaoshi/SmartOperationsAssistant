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
