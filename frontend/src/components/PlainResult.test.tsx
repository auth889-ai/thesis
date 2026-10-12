import {render, screen} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {describe, expect, it} from "vitest";

import {I18nProvider} from "@/i18n";
import {PlainResult} from "./PlainResult";

describe("a plain result", () => {
  it("shows the sentence, the tag word and the link to Research", () => {
    render(<MemoryRouter><I18nProvider><PlainResult kind="simulated" to="/lab/evidence">An ambulance can arrive sooner.</PlainResult></I18nProvider></MemoryRouter>);
    expect(screen.getByText("An ambulance can arrive sooner.")).toBeInTheDocument();
    expect(screen.getByText("Simulation")).toBeInTheDocument();
    expect(screen.getByRole("link", {name: /how we know/i})).toHaveAttribute("href", "/lab/evidence");
  });
});
