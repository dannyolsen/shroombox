use yew::prelude::*;

#[function_component(PhaseSelector)]
pub fn phase_selector() -> Html {
    let phase = use_state(|| String::from("growing"));
    
    let on_phase_change = {
        let phase = phase.clone();
        Callback::from(move |e: Event| {
            let value = e.target_unchecked_into::<HtmlSelectElement>().value();
            // Update backend
            spawn_local(async move {
                let resp = Request::post("/api/phase")
                    .json(&json!({ "phase": value }))
                    .send()
                    .await;
                if resp.is_ok() {
                    phase.set(value);
                }
            });
        })
    };

    html! {
        <select onchange={on_phase_change}>
            <option value="colonisation" selected={*phase == "colonisation"}>{"Colonisation"}</option>
            <option value="growing" selected={*phase == "growing"}>{"Growing"}</option>
            <option value="cake" selected={*phase == "cake"}>{"Cake"}</option>
        </select>
    }
} 