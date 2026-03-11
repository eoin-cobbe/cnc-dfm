import SwiftUI

struct SettingsView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                PanelCard(title: "Shared Config", subtitle: "These values write to the same backend config used by the CLI.") {
                    HStack(spacing: 12) {
                        Button("Reload") {
                            Task {
                                await model.bootstrap()
                            }
                        }
                        .buttonStyle(.bordered)

                        Button("Reset Changes") {
                            model.resetDraftToSaved()
                        }
                        .buttonStyle(.bordered)
                        .disabled(!model.settingsAreDirty)

                        Spacer()

                        Button {
                            Task {
                                await model.saveSettings()
                            }
                        } label: {
                            if model.isSavingSettings {
                                ProgressView()
                                    .controlSize(.small)
                            } else {
                                Text("Save Config")
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(!model.settingsAreDirty || model.isSavingSettings || model.configDraft == nil)
                    }
                }

                if let draft = model.configDraft {
                    PanelCard(title: "Rule Thresholds") {
                        Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 12) {
                            GridRow {
                                numericField("Rule 1 Min Radius", value: binding(\.minRadius))
                                numericField("Rule 2 Max Pocket Ratio", value: binding(\.maxPocketRatio))
                            }
                            GridRow {
                                numericField("Rule 3 Min Wall", value: binding(\.minWall))
                                numericField("Rule 4 Max Hole Ratio", value: binding(\.maxHoleRatio))
                            }
                            GridRow {
                                integerField("Rule 5 Max Setups", value: binding(\.maxSetups))
                                numericField("Rule 6 Max Tool Depth Ratio", value: binding(\.maxToolDepthRatio))
                            }
                        }
                    }

                    PanelCard(title: "Material And Machine") {
                        Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 12) {
                            GridRow {
                                materialPicker(selected: binding(\.material))
                                numericField("Billet Cost (EUR/kg)", value: binding(\.materialBilletCostEurPerKg))
                            }
                            GridRow {
                                numericField("Baseline 6061 MRR", value: binding(\.baseline6061Mrr))
                                numericField("3-Axis Hourly Rate", value: binding(\.machineHourlyRate3AxisEur))
                            }
                            GridRow {
                                numericField("5-Axis Hourly Rate", value: binding(\.machineHourlyRate5AxisEur))
                                numericField("Surface Penalty Slope", value: binding(\.surfacePenaltySlope))
                            }
                        }
                    }

                    PanelCard(title: "Multiplier Controls") {
                        Grid(alignment: .leading, horizontalSpacing: 18, verticalSpacing: 12) {
                            GridRow {
                                numericField("Surface Penalty Max", value: binding(\.surfacePenaltyMaxMultiplier))
                                numericField("Complexity Penalty / Face", value: binding(\.complexityPenaltyPerFace))
                            }
                            GridRow {
                                numericField("Complexity Penalty Max", value: binding(\.complexityPenaltyMaxMultiplier))
                                integerField("Complexity Baseline Faces", value: binding(\.complexityBaselineFaces))
                            }
                            GridRow {
                                numericField("Hole Penalty / Feature", value: binding(\.holeCountPenaltyPerFeature))
                                numericField("Hole Penalty Max", value: binding(\.holeCountPenaltyMaxMultiplier))
                            }
                            GridRow {
                                numericField("Radius Penalty / Feature", value: binding(\.radiusCountPenaltyPerFeature))
                                numericField("Radius Penalty Max", value: binding(\.radiusCountPenaltyMaxMultiplier))
                            }
                            GridRow {
                                numericField("Quantity Learning Rate", value: binding(\.qtyLearningRate))
                                numericField("Quantity Floor", value: binding(\.qtyFactorFloor))
                            }
                        }
                    }

                    PanelCard(title: "Current Selection", subtitle: "Saved config path and material baseline context.") {
                        VStack(alignment: .leading, spacing: 10) {
                            keyValueRow("Config Path", model.health?.configPath ?? "Unavailable")
                            if let material = model.availableMaterials.first(where: { $0.key == draft.material }) {
                                keyValueRow("Material", material.label)
                                keyValueRow("Machinability Source", material.machinabilitySource)
                                keyValueRow("Billet Cost Source", material.baselineBilletCostSource)
                            }
                        }
                    }
                } else {
                    ProgressView("Loading config…")
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding(.top, 60)
                }
            }
            .padding(24)
        }
    }

    private func materialPicker(selected: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Material")
                .font(.caption.weight(.medium))
                .foregroundStyle(AppTheme.mutedText)
            Picker("Material", selection: selected) {
                ForEach(model.availableMaterials) { material in
                    Text(material.label).tag(material.key)
                }
            }
            .labelsHidden()
            .pickerStyle(.menu)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func numericField(_ title: String, value: Binding<Double>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption.weight(.medium))
                .foregroundStyle(AppTheme.mutedText)
            TextField(title, value: value, format: .number.precision(.fractionLength(3)))
                .textFieldStyle(.roundedBorder)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func integerField(_ title: String, value: Binding<Int>) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption.weight(.medium))
                .foregroundStyle(AppTheme.mutedText)
            TextField(title, value: value, format: .number.grouping(.never))
                .textFieldStyle(.roundedBorder)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func keyValueRow(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(.caption2.weight(.medium))
                .foregroundStyle(AppTheme.mutedText)
            Text(value)
                .font(.subheadline)
                .textSelection(.enabled)
        }
    }

    private func binding(_ keyPath: WritableKeyPath<ConfigValues, Double>) -> Binding<Double> {
        Binding(
            get: { model.configDraft?[keyPath: keyPath] ?? 0.0 },
            set: { newValue in
                model.configDraft?[keyPath: keyPath] = newValue
            }
        )
    }

    private func binding(_ keyPath: WritableKeyPath<ConfigValues, Int>) -> Binding<Int> {
        Binding(
            get: { model.configDraft?[keyPath: keyPath] ?? 0 },
            set: { newValue in
                model.configDraft?[keyPath: keyPath] = newValue
            }
        )
    }

    private func binding(_ keyPath: WritableKeyPath<ConfigValues, String>) -> Binding<String> {
        Binding(
            get: { model.configDraft?[keyPath: keyPath] ?? "" },
            set: { newValue in
                model.configDraft?[keyPath: keyPath] = newValue
            }
        )
    }
}
