export const chapters = [
  { id: "introduccion", title: "Introducción" },
  { id: "problema", title: "Problema y objetivos" },
  { id: "metodologia", title: "Metodología" },
  { id: "arquitectura", title: "Datos y arquitectura" },
  { id: "decisiones", title: "Decisiones técnicas" },
  { id: "evaluacion", title: "Evaluación" },
  { id: "conclusiones", title: "Conclusiones" },
  { id: "referencias", title: "Referencias" },
] as const;

export const team = [
  { name: "Esdras de la Torre Valdivia", role: "Scrum Master · Desarrollo" },
  { name: "Adrián Lago Aponte", role: "Product Owner · Desarrollo" },
  { name: "Oscar Arturo Lopez Cordova", role: "Desarrollo" },
];

export const survey = [
  { label: "Valora la utilidad de un primer borrador con 4 o 5 puntos", percent: 92.3, count: 12 },
  { label: "Usa IA ocasional o frecuentemente", percent: 84.6, count: 11 },
  { label: "Se preocupa por datos inventados o cálculos incorrectos", percent: 76.9, count: 10 },
  { label: "Dedica 30 minutos o más a concluir y enviar el menú", percent: 61.5, count: 8 },
];

export const backlog = [
  ["HU01", "Registrar datos del paciente", "Alta", "3", "Campos completos y persistencia estructurada."],
  ["HU02", "Calcular requerimientos nutricionales", "Alta", "8", "Fórmulas visibles y comparación con cálculo manual."],
  ["HU03", "Generar el primer borrador", "Alta", "8", "Correspondencia con el paciente y estructura solicitada."],
  ["HU04", "Consultar las fuentes", "Alta", "5", "Documentos y datos accesibles para su revisión."],
  ["HU05", "Mostrar alertas sobre restricciones", "Alta", "8", "Aviso visible ante una restricción declarada."],
  ["HU06", "Editar alimentos y cantidades", "Alta", "5", "Edición disponible para el profesional."],
  ["HU07", "Solicitar una nueva generación", "Media", "3", "Instrucciones adicionales reflejadas en otro borrador."],
  ["HU08", "Aprobar o rechazar el plan", "Alta", "3", "Decisión explícita del profesional."],
  ["HU09", "Exportar el plan terminado", "Media", "5", "Archivo generado y revisable."],
];

export const decisions = [
  {
    title: "Separar cálculo y generación",
    obstacle: "Una respuesta lingüísticamente convincente puede contener errores aritméticos o nutricionales.",
    decision: "El motor Python calcula los requerimientos; BAM aporta datos tabulares y el LLM propone el borrador. Pydantic valida la estructura y las reglas deterministas revisan el plan.",
    tradeoff: "La reproducibilidad numérica mejora, pero las reglas fijas del MVP no equivalen a una prescripción individualizada. Los valores sin coincidencia fiable en BAM siguen necesitando revisión.",
  },
  {
    title: "Recuperar evidencia con procedencia",
    obstacle: "El conocimiento interno del modelo no permite identificar de manera suficiente la fuente de cada recomendación.",
    decision: "Un manifiesto controla los documentos autorizados. LlamaIndex y Qdrant recuperan fragmentos con identidad documental y los vinculan con el intento de generación.",
    tradeoff: "Recuperar un texto no demuestra que respalde una afirmación. La cobertura del corpus, la extracción y la pertinencia de cada fragmento requieren evaluación profesional.",
  },
  {
    title: "Tratar PDF y tabla como datos distintos",
    obstacle: "Un PDF escaneado puede no contener texto extraíble; los nombres, unidades y porciones de una tabla pueden ser ambiguos.",
    decision: "El lector pypdf extrae texto y descarta documentos vacíos. El adaptador BAM comprueba columnas, normaliza nombres para búsqueda y escala valores por 100 g solo con coincidencia exacta normalizada y unidad en gramos.",
    tradeoff: "No hay un OCR general integrado ni conversión automática fiable de todas las medidas caseras. Disponer del PDF del SMAE no implementa por sí solo un motor de equivalentes.",
  },
  {
    title: "Ejecutar el modelo localmente",
    obstacle: "El prototipo necesita una configuración reproducible compatible con los recursos de desarrollo disponibles.",
    decision: "La configuración local utiliza Ollama con llama3.2:3b y Docker Compose. La propuesta inicial mencionaba vLLM; la implementación revisada utiliza Ollama detrás de un cliente compatible con la API de chat.",
    tradeoff: "La ejecución en CPU reduce requisitos de hardware, pero aumenta la latencia. Un despliegue local no garantiza por sí mismo confidencialidad: faltan controles de acceso, protección del almacenamiento y políticas de operación para uso real.",
  },
  {
    title: "Conservar versiones y revisión humana",
    obstacle: "Editar o regenerar puede borrar la relación entre el primer borrador, las correcciones y la decisión final.",
    decision: "Prisma y SQLite separan paciente, consulta, cálculo, plan y generación. Se registran versiones, fuentes recuperadas, validaciones y cambios; la aprobación exige la intervención del profesional.",
    tradeoff: "La trazabilidad técnica facilita auditar el flujo, pero el actor de demostración no sustituye una identidad autenticada. La concurrencia y la gobernanza deben ampliarse antes de un despliegue multiusuario.",
  },
  {
    title: "Hacer explícitas las brechas del prototipo",
    obstacle: "La amplitud de las necesidades detectadas supera lo verificable en un MVP académico.",
    decision: "El alcance de investigación se limita a adultos sin patologías complejas. Se documentan por separado las metas de la entrega, los umbrales del código y la evidencia que falta reunir.",
    tradeoff: "Las alertas por coincidencia de términos no cubren todas las alergias ni las interacciones fármaco-alimento. No se afirma seguridad clínica integral, validación SMAE automatizada ni reducción de tiempos demostrada.",
  },
];

export const references = [
  { id: "ref-azimi", author: "Azimi, I., Qi, M., Wang, L., Rahmani, A. M., & Li, Y.", year: "2025", title: "Evaluation of LLMs accuracy and consistency in the registered dietitian exam through prompt engineering and knowledge retrieval.", publication: "Scientific Reports, 15, 1506.", href: "https://doi.org/10.1038/s41598-024-85003-w" },
  { id: "ref-bragazzi", author: "Bragazzi, N. L., Monica, S., Bergenti, F., Scazzina, F., & Rosi, A.", year: "2025", title: "Comparative analysis of AI on human nutrition knowledge: Evaluating large language model-based conversational agents against dietetics students and the general population.", publication: "PLOS One, 20(12), e0336577.", href: "https://doi.org/10.1371/journal.pone.0336577" },
  { id: "ref-entrega1", author: "Equipo 3033E.", year: "2026a", title: "Planes dietéticos asistidos por modelos de lenguaje grande bajo supervisión de nutriólogos. Entrega 1.", publication: "UNIR. Trabajo académico del equipo, 22 de julio de 2026." },
  { id: "ref-entrega2", author: "Equipo 3033E.", year: "2026b", title: "Planes dietéticos asistidos por modelos de lenguaje grande bajo supervisión de nutriólogos. Entrega 2.", publication: "UNIR. Trabajo académico del equipo. Objetivos: pp. 8–9; encuesta y selección: pp. 10–31; metodología: pp. 32–44." },
  { id: "ref-prototipo", author: "Equipo 3033E.", year: "s. f.", title: "Selección de prototipo y criterio para hacerlo.", publication: "Documento de trabajo interno, versión «ala». Criterios y matriz ponderada." },
  { id: "ref-lewis", author: "Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W.-t., Rocktäschel, T., Riedel, S., & Kiela, D.", year: "2020", title: "Retrieval-augmented generation for knowledge-intensive NLP tasks.", publication: "Advances in Neural Information Processing Systems, 33, 9459–9474.", href: "https://arxiv.org/abs/2005.11401" },
  { id: "ref-lean", author: "The Lean Startup.", year: "s. f.", title: "Methodology.", publication: "Principios del ciclo construir–medir–aprender.", href: "https://theleanstartup.com/principles" },
  { id: "ref-scrum", author: "Schwaber, K., & Sutherland, J.", year: "2020", title: "The Scrum Guide.", publication: "Guía de Scrum, noviembre de 2020.", href: "https://scrumguides.org/scrum-guide.html" },
  { id: "ref-guia", author: "Universidad Internacional de La Rioja.", year: "s. f.-a", title: "Guía del Trabajo de Investigación. Maestría en Inteligencia Artificial.", publication: "Material de la asignatura. Los archivos «guia.pdf» y «guia seminario de innovacion en IA.pdf» contienen la misma guía." },
  { id: "ref-instrucciones", author: "Universidad Internacional de La Rioja.", year: "s. f.-b", title: "Instrucciones para la redacción y elaboración del documento del Trabajo de Innovación.", publication: "Material de la asignatura, pp. 9–13." },
  { id: "ref-rubrica", author: "Universidad Internacional de La Rioja.", year: "s. f.-c", title: "Rúbrica de evaluación del Trabajo de Innovación.", publication: "Material de la asignatura." },
];
