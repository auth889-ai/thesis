import {useState} from "react";

import {Tabs} from "@/components/Tabs";
import {Card, Loading} from "@/components/ui";
import {DataTab} from "./DataTab";
import {useNetwork, useRegistry, useRoad, useTrained} from "./hooks";
import {ModelStatus} from "./ModelStatus";
import {ModelsTab} from "./ModelsTab";
import {TrainTab} from "./TrainTab";
import {DatasetSelect, useDataset} from "./useDataset";
import {ValidationTab} from "./ValidationTab";
import "./forecast.css";

type Tab = "models" | "validation" | "train" | "data";
const TABS: {key: Tab; label: string}[] = [{key: "models", label: "Models"}, {key: "validation", label: "Validation"}, {key: "train", label: "Train"}, {key: "data", label: "Data"}];

/** LAB · MODELS: the model behind the city map with its verified facts, every model compared, held-out validation, training and upload. */
export function ModelsPage() {
  const {datasets, ds, setDsId, asOf, refresh} = useDataset();
  const [tab, setTab] = useState<Tab>("models");
  const net = useNetwork(ds, asOf);
  const registry = useRegistry(ds?.id);
  const trained = useTrained();
  const first = net.data?.sensors.find((s) => s.mapped_edge)?.node ?? null;
  const road = useRoad(ds?.id, first, asOf);
  const trainedCard = (trained.data?.trained ?? []).find((t: any) => t.dataset === ds?.id && t.arch === "GWNet") ?? (trained.data?.trained ?? []).find((t: any) => t.dataset === ds?.id) ?? null;
  if (!datasets.data) return <Loading what="loading the datasets" />;
  if (!ds) return <div className="note warn">No dataset is available.</div>;
  return (
    <div className="stack tf">
      <div className="row tf-head"><DatasetSelect datasets={datasets.data} value={ds.id} onChange={setDsId} /><Tabs items={TABS} value={tab} onChange={setTab} /></div>
      <Card title="The model behind the city map" sub="checkpoint, hashes and the fresh inference of the latest request">{net.data ? <ModelStatus net={net.data} registry={registry.data} /> : <Loading />}</Card>
      {tab === "models" && <ModelsTab ds={ds} road={road.data ?? null} asOf={asOf} />}
      {tab === "validation" && <ValidationTab ds={ds} net={net.data ?? null} registry={registry.data} trainedCard={trainedCard} />}
      {tab === "train" && <TrainTab ds={ds} onTrained={refresh} />}
      {tab === "data" && <DataTab ds={ds} onUploaded={(id) => { refresh(); setDsId(id); setTab("models"); }} />}
    </div>
  );
}
