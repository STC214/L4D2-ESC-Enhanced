#pragma once
#include <cstddef>
#include <cstring>

// Read-only layout prefix from the L4D2 HL2SDK ConCommandBase/ConVar ABI.
// No flags, vtables or raw values are patched. Writes use IConVar::SetValue.
struct CommandPrefix {
    void* table;
    void* next;
    bool registered;
    const char* name;
    const char* help;
    int flags;
};
struct CvarPrefix {
    CommandPrefix base;
    void* interface_table;
    CvarPrefix* parent;
    const char* default_value;
    char* string_value;
    int string_length;
    float float_value;
    int int_value;
};
static_assert(sizeof(CommandPrefix) == 24, "Pinned x86 ConCommandBase ABI");
static_assert(offsetof(CvarPrefix, parent) == 28 && offsetof(CvarPrefix, int_value) == 48,
              "Pinned x86 ConVar value prefix");

class LocalIConVar {
public:
    virtual void SetValue(const char*) = 0;
    virtual void SetValue(float) = 0;
    virtual void SetValue(int) = 0;
    virtual void SetColor(unsigned int) = 0;
    virtual const char* GetName() const = 0;
    virtual const char* GetBaseName() const = 0;
    virtual bool IsFlagSet(int) const = 0;
    virtual int GetSplitScreenPlayerSlot() const = 0;
};

inline bool SetCheckedLocalInt(CvarPrefix* var, const char* name, int value, bool outline_default = false) {
    if (!var || !var->parent || var->parent->parent != var->parent) return false;
    // Explicit one-shot outline defaults only. No flag removal or enforcement;
    // a remote server may subsequently overwrite these replicated values.
    const bool outline_zero = outline_default && value == 0 && name &&
        (!std::strcmp(name, "sv_disable_glow_survivors") || !std::strcmp(name, "sv_disable_glow_faritems"));
    if (outline_default && !outline_zero) return false;
    if (((var->base.flags | var->parent->base.flags) & (1 << 13)) && !outline_zero) return false;
    auto iface = reinterpret_cast<LocalIConVar*>(reinterpret_cast<char*>(var) + sizeof(CommandPrefix));
    const char* actual = iface->GetName();
    if (!actual || std::strcmp(actual, name)) return false;
    const int flags = var->base.flags, parent_flags = var->parent->base.flags;
    iface->SetValue(value);
    return var->parent->int_value == value && var->base.flags == flags &&
           var->parent->base.flags == parent_flags;
}
