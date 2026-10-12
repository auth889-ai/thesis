import {useSearchParams} from "react-router-dom";

import {AddCityCard} from "./AddCityCard";

/** ADD CITY: the Add your city card on its own page. The go-anywhere search sends a name here as ?name=. */
export function AddCityPage() {
  const [params] = useSearchParams();
  const name = params.get("name") ?? "";
  return <AddCityCard key={name} initialName={name} />;
}
