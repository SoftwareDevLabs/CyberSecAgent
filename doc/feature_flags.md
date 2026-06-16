# til::feature

Feature flags are controlled by an XML document stored at `src/features.xml`.

## Notes

Features that are disabled for Release using `alwaysDisabledReleaseTokens` are
*always* disabled in Release, even if they come from a branch that would have
been enabled by the wildcard.

### Precedence

1. `alwaysDisabledReleaseTokens`
2. Enabled branches
3. Disabled branches
   * The longest branch token that matches your branch will win.
3. Enabled brandings
4. Disabled brandings
5. The feature's default state
