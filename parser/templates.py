from drain3.template_miner_config import TemplateMinerConfig
from drain3.template_miner import TemplateMiner
from threading import Lock

from parser.preprocess import mask


class TemplateStore:
    def __init__(self):
        self.lock = Lock()
        self.config = TemplateMinerConfig()
        self.miners = {}

    def parse_lines(self, lines) -> list[dict]:
        # each line is {"source": ..., "text":...}
        if not lines:
            return []

        counts = {}
        with self.lock:
            for line in lines:
                # skip all stack traces lines which start with \t
                if line["text"].startswith("\t"):
                    continue
                if line["source"] not in self.miners:  # faster than setdefault()
                    self.miners[line["source"]] = TemplateMiner(
                        config=self.config)
                tm = self.miners[line["source"]]
                cid = tm.add_log_message(mask(line["text"]))["cluster_id"]
                counts.setdefault((line["source"], cid), 0)
                counts[(line["source"], cid)] += 1

            results = []
            # expected format of result: {"source":..., "id":..., "template":..., "count":...}
            for (source, cid) in counts.keys():
                count = counts[(source, cid)]
                template = self.miners[source].drain.id_to_cluster[cid].get_template(
                )
                results.append({"source": source, "id": str(
                    cid), "template": template, "count": count})

            return results
