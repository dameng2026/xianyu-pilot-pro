const els = document.querySelectorAll('[class*=message], [class*=chat], [class*=bubble]');
const result = [];
els.forEach(el => {
  const text = el.innerText?.trim();
  if (text && text.length > 5 && text.length < 500) {
    result.push({class: el.className.substring(0,80), text: text.substring(0,200)});
  }
});
JSON.stringify(result.slice(0, 20), null, 2);
