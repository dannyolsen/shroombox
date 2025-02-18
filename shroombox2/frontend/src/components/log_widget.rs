use yew::prelude::*;
use gloo_events::EventSource;

#[function_component(LogViewer)]
pub fn log_viewer() -> Html {
    let logs = use_state(Vec::new);
    
    use_effect_with_deps(
        move |_| {
            let event_source = EventSource::new("/api/logs").unwrap();
            let logs = logs.clone();
            
            event_source.add_event_listener("message", move |e: MessageEvent| {
                let new_log = e.data().as_string().unwrap();
                logs.update(|l| {
                    let mut new_logs = l.clone();
                    new_logs.push(new_log);
                    if new_logs.len() > 100 {
                        new_logs.remove(0);
                    }
                    new_logs
                });
            });

            || {
                event_source.close();
            }
        },
        (),
    );

    html! {
        <div id="log-container">
            <pre id="logs">
                {for logs.iter().map(|log| html! {
                    <div class="log-line">{log}</div>
                })}
            </pre>
        </div>
    }
} 