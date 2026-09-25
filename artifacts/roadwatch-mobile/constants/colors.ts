/**
 * Semantic design tokens for the mobile app.
 *
 * These tokens mirror the naming conventions used in web artifacts (index.css)
 * so that multi-artifact projects share a cohesive visual identity.
 *
 * Replace the placeholder values below with values that match the project's
 * brand. If a sibling web artifact exists, read its index.css and convert the
 * HSL values to hex so both artifacts use the same palette.
 *
 * To add dark mode, add a `dark` key with the same token names.
 * The useColors() hook will automatically pick it up.
 */

const colors = {
  light: {
    text: '#1B3037',
    tint: '#176F75',
    background: '#F2F3ED',
    foreground: '#1B3037',
    card: '#FBFCF7',
    cardForeground: '#1B3037',
    primary: '#176F75',
    primaryForeground: '#F8FAF5',
    secondary: '#E2EAE6',
    secondaryForeground: '#294A4D',
    muted: '#E9EDE7',
    mutedForeground: '#627578',
    accent: '#DCEFEB',
    accentForeground: '#155D62',
    destructive: '#B64D3B',
    destructiveForeground: '#FFF9F3',
    border: '#D4DED8',
    input: '#D4DED8',
    ink: '#152B32',
    inkSoft: '#29434A',
    signal: '#D68153',
    signalPale: '#F8E9DE',
    success: '#3D7460',
    grid: '#405A60',
  },
  radius: 14,
};

export default colors;
