// Substitua URL absoluta por relativa
// Trecho relevante: linha que faz POST /api/logistics/upload
fetch('/api/logistics/upload', {
  method: 'POST',
  body: formData
}).then(res => /* ... */)
