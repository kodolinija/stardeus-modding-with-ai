using Game.Components;
using Game.Utils;
using KL.Utils;

namespace __NAMESPACE__ {
    // A component that defs can use. The component name is the class name without "Comp":
    // { "Component" : "__COMPONENT__", "Properties" : [ { "Key" : "Message", "String" : "Hi" } ] }
    // Component names are global, so keep the mod's name in them.
    public sealed class __COMPONENT__Comp : BaseComponent<__COMPONENT__Comp> {
        // Property keys are hashed strings. Keys the game already uses are in PropertyIdH.
        private static readonly int MessageH = Hashes.S("Message");

        // [SelfInit] methods run while the game loads; this one registers the component.
        [SelfInit]
        private static void Register() {
            AddComponentPrototype(new __COMPONENT__Comp());
        }

        private string message;

        // Reads the def's Properties; runs for new and loaded entities alike
        protected override void OnConfig() {
            message = Config.GetString(MessageH, "Hello from __ID__");
        }

        // Runs when all components of the entity are ready; wasLoaded is true after loading a save
        public override void OnLateReady(bool wasLoaded) {
            if (!wasLoaded) {
                D.Warn("{0}: {1}", Entity, message);
            }
        }
    }
}
