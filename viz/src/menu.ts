// The menu page: live run, replay, scenario creation (coming soon) and settings.
import { translate } from './i18n';
import { applyTheme } from './prefs';

// Old links (`/?replay=…`, `/?ws=…`) open the viewer as they used to.
const params = new URLSearchParams(location.search);
if (params.has('replay') || params.has('ws') || params.has('live')) {
  location.replace('/view.html' + location.search);
}
applyTheme();
translate();
