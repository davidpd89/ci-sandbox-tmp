# Revision de arquitectura, limites y acoplamiento

Investigar analizadores publicos de dependencias, ciclos, capas, fan-in/fan-out y
arquitectura evolutiva para Python.

Construir el grafo real de imports y llamadas entre dominio comun, adaptadores,
UI, almacenamiento y operacion. Localizar ciclos, imports laterales y modulos
centrales demasiado amplios. Proponer y ejecutar una mejora acotada con tests que
protejan el nuevo limite arquitectonico.
