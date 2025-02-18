use yew::prelude::*;
use gloo_net::http::Request;
use serde::{Deserialize, Serialize};

// Define our main state structures
#[derive(Serialize, Deserialize, Clone, PartialEq)]
pub struct SystemStatus {
    running: bool,
    pid: Option<i32>,
}

#[derive(Properties, PartialEq)]
pub struct WidgetProps {
    pub title: String,
    pub children: Children,
}

// Main App Component
#[function_component(App)]
pub fn app() -> Html {
    let status = use_state(|| SystemStatus { running: false, pid: None });
    let grid = use_node_ref();

    // Initialize GridStack
    use_effect_with_deps(
        move |_| {
            let grid_options = GridStack::init(GridStackOptions {
                cell_height: 60,
                margin: 10,
                animate: true,
                float: true,
                // ... other options
            });
            
            // Save cleanup function
            || {
                // Cleanup code
            }
        },
        (),
    );

    html! {
        <>
            // Control Panel
            <div class="control-panel">
                <ControlPanel status={(*status).clone()} />
            </div>

            // Grid Layout
            <div class="grid-stack" ref={grid}>
                // Phase Selection Widget
                <Widget title="Current Phase">
                    <PhaseSelector />
                </Widget>

                // Phase Settings Widget
                <Widget title="Phase Settings">
                    <PhaseSettings />
                </Widget>

                // Humidifier Settings Widget
                <Widget title="Humidifier Settings">
                    <HumidifierSettings />
                </Widget>

                // PID Settings Widget
                <Widget title="PID Settings">
                    <PidSettings />
                </Widget>

                // System Logs Widget
                <Widget title="System Logs">
                    <LogViewer />
                </Widget>
            </div>
        </>
    }
} 