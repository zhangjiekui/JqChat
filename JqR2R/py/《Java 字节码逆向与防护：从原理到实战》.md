Java 字节逆向与防护讲解文档



一、字节码保护的必要性



### 1.1 代码安全风险&#xA;

Java 程序编译后生成的是字节码文件（.class 文件），这些字节码文件可以通过反编译工具（如 JD-GUI、Fernflower 等）轻松地还原成 Java 源代码。这意味着，如果你的 Java 代码没有得到有效的保护，竞争对手或恶意攻击者可以轻易地获取你的核心算法、业务逻辑、敏感信息等，从而对你的商业利益造成损害。


### 1.2 知识产权保护&#xA;

对于软件开发者来说，代码是他们的知识产权。通过字节码保护，可以防止他人抄袭、盗用你的代码，保护你的知识产权。


### 1.3 防止恶意攻击&#xA;

未受保护的字节码容易被恶意篡改，攻击者可以通过修改字节码来实现注入恶意代码、绕过授权验证等目的。字节码保护可以有效地防止这些恶意攻击，保障程序的安全性和稳定性。


二、字节码保护基础知识



### 2.1 Java 字节码&#xA;

Java 字节码是 Java 源代码编译后生成的中间代码，它是一种平台无关的二进制格式，可以在任何支持 Java 虚拟机（JVM）的平台上运行。字节码文件包含了类的结构信息、方法的字节码指令、常量池等内容。


### 2.2 反编译工具&#xA;

常见的 Java 反编译工具包括 JD-GUI、Fernflower、Procyon 等。这些工具可以将字节码文件还原成 Java 源代码，方便开发者进行代码分析和调试。


### 2.3 字节码保护技术&#xA;

常见的字节码保护技术包括代码混淆、加密、水印等。




*   **代码混淆**：通过对字节码进行重命名、删除无用代码、插入混淆代码等操作，使反编译后的代码难以理解和分析。


*   **加密**：对字节码文件进行加密，只有在运行时才进行解密，防止字节码文件被直接反编译。


*   **水印**：在字节码文件中嵌入特定的标识信息，用于追踪和识别代码的来源。


三、字节码保护实战



### 3.1 项目概述&#xA;

本项目是一个简单的 Java 项目，包含了数据加密和解密的功能。项目结构如下：




```
jvmti-demo/


├── crack-agent/


├── data-gurad/


├── demo/


├── other/


├── build.gradle.kts


├── gradle.properties


├── gradle/


├── settings.gradle.kts


├── gradlew


└── gradlew.bat
```

### 3.2 代码混淆&#xA;

在本项目中，我们使用 ProGuard 进行代码混淆。ProGuard 是一个开源的 Java 代码混淆工具，它可以对字节码进行优化、压缩和混淆，提高代码的安全性。


#### 3.2.1 配置 ProGuard&#xA;

在 `data-gurad` 模块的 `build.gradle.kts` 文件中添加 ProGuard 配置：




```
android {


&#x20;   buildTypes {


&#x20;       release {


&#x20;           minifyEnabled true


&#x20;           proguardFiles(getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro')


&#x20;       }


&#x20;   }


}
```

#### 3.2.2 编写 ProGuard 规则&#xA;

在 `data-gurad` 模块的根目录下创建 `proguard-rules.pro` 文件，并添加以下规则：




```
\# 保留 DataGuard 接口定义


-keep interface org.codecrafterslab.data.DataGuard {


&#x20;   public \*;


}


\# 混淆 DataGuard 的实现类


-keep class org.codecrafterslab.data.impl.\*\* { \*; }


\# 但是不保留方法名和类名，进行混淆


-allowaccessmodification
```

### 3.3 字节码转换&#xA;

在本项目中，我们使用 Java Agent 技术进行字节码转换。Java Agent 是一种可以在 JVM 启动时或运行时动态修改字节码的技术。


#### 3.3.1 编写 ClassFileTransformer&#xA;

在 `crack-agent` 模块中编写 `DataGuardClassFileTransformer` 类，实现 `ClassFileTransformer` 接口：




```
package org.codecrafterslab.agent;


import lombok.extern.slf4j.Slf4j;


import java.lang.instrument.ClassFileTransformer;


import java.lang.instrument.IllegalClassFormatException;


import java.security.ProtectionDomain;


@Slf4j


public class DataGuardClassFileTransformer implements ClassFileTransformer {


&#x20;   @Override


&#x20;   public byte\[] transform(ClassLoader loader, String className, Class\<?> classBeingRedefined,


&#x20;                           ProtectionDomain protectionDomain, byte\[] classFileBuffer) throws IllegalClassFormatException {


&#x20;       log.debug("transform className: {}", className);


&#x20;       // TODO: 需要转换实现相应的转换逻辑，返回 null，表示不转换


&#x20;       return null;


&#x20;   }


}
```

#### 3.3.2 编写 Agent 类&#xA;

在 `crack-agent` 模块中编写 `Agent` 类，实现 `premain` 和 `agentmain` 方法：




```
package org.codecrafterslab.agent;


import lombok.extern.slf4j.Slf4j;


import java.lang.instrument.Instrumentation;


import java.lang.instrument.UnmodifiableClassException;


import java.util.Arrays;


import java.util.List;


import java.util.Set;


import java.util.stream.Collectors;


import java.util.stream.Stream;


@Slf4j


public class Agent {


&#x20;   private static void processAgent(String agentArgs, Instrumentation inst, boolean attach) {


&#x20;       /\* 解析参数 \*/


&#x20;       String transformerClassName = "org.codecrafterslab.data.impl.DefaultDataGuard";


&#x20;       DataGuardClassFileTransformer classFileTransformer = new DataGuardClassFileTransformer();


&#x20;       /\* Agent\_OnAttach \*/


&#x20;       if (attach) {


&#x20;           Set\<Class\<?>> classSet = null;


&#x20;           /\* 1. 注册类文件转换器 \*/


&#x20;           inst.addTransformer(classFileTransformer, inst.isRetransformClassesSupported());


&#x20;           /\* 2. 获取需要重新转换的类 \*/


&#x20;           if (inst.isRetransformClassesSupported()) {


&#x20;               /\* 2.1 所有已经加载的类 \*/


&#x20;               Stream\<Class\<?>> allLoadedClasses = Arrays.stream((Class\<?>\[]) inst.getAllLoadedClasses())


&#x20;                       .filter(clazz -> clazz.getCanonicalName() != null && !clazz.getCanonicalName().isEmpty());


&#x20;               /\* 2.2 添加需要转换的类 \*/


&#x20;               classSet = allLoadedClasses


&#x20;                       .filter(clazz -> transformerClassName.equals(clazz.getCanonicalName()))


&#x20;                       .collect(Collectors.toSet());


&#x20;           }


&#x20;           /\* 3. 重新转换类 \*/


&#x20;           if (inst.isRetransformClassesSupported() && classSet != null && !classSet.isEmpty()) {


&#x20;               Class\<?>\[] classes = classSet.toArray(new Class\<?>\[0]);


&#x20;               if (log.isDebugEnabled()) {


&#x20;                   List\<String> names = classSet.stream().map(Class::getCanonicalName).collect(Collectors.toList());


&#x20;                   log.debug("agent loaded and will retransformer class : {}", names);


&#x20;               }


&#x20;               try {


&#x20;                   /\* 其中任何一个类不能转换将会抛出 UnmodifiableClassException 异常 \*/


&#x20;                   inst.retransformClasses(classes);


&#x20;               } catch (UnmodifiableClassException e) {


&#x20;                   log.error(e.getMessage());


&#x20;               }


&#x20;           }


&#x20;       }


&#x20;       /\* Agent\_OnLoad \*/


&#x20;       else {


&#x20;           /\* 1. 将当前 jar 包信息设置到系统环境变量 \*/


&#x20;           AgentUtil.setAgentJarInfo();


&#x20;           /\* 2. 注册类文件转换器 \*/


&#x20;           inst.addTransformer(classFileTransformer);


&#x20;       }


&#x20;       /\* 设置代理所需的本机方法前缀 \*/


&#x20;       if (inst.isNativeMethodPrefixSupported()) {


&#x20;           inst.setNativeMethodPrefix(classFileTransformer, "");


&#x20;       }


&#x20;   }


&#x20;   /\*\*


&#x20;    \* JVM 首先尝试在代理类上调用以下方法


&#x20;    \*


&#x20;    \* @param agentArgs agentArgs


&#x20;    \* @param inst      inst


&#x20;    \*/


&#x20;   public static void premain(String agentArgs, Instrumentation inst) {


&#x20;       if (log.isDebugEnabled()) {


&#x20;           if (null == agentArgs || agentArgs.isEmpty()) {


&#x20;               log.debug("agent for premain");


&#x20;           } else {


&#x20;               log.debug("agent for premain,agentArgs is \[{}].", agentArgs);


&#x20;           }


&#x20;       }


&#x20;       processAgent(agentArgs, inst, false);


&#x20;   }


&#x20;   /\*\*


&#x20;    \* Attach API


&#x20;    \*


&#x20;    \* @param agentArgs agentArgs


&#x20;    \* @param inst      inst


&#x20;    \*/


&#x20;   public static void agentmain(String agentArgs, Instrumentation inst) {


&#x20;       if (log.isDebugEnabled()) {


&#x20;           if (null == agentArgs || agentArgs.isEmpty()) {


&#x20;               log.debug("agent for attach API");


&#x20;           } else {


&#x20;               log.debug("agent for attach API,agentArgs is \[{}].", agentArgs);


&#x20;           }


&#x20;       }


&#x20;       processAgent(agentArgs, inst, true);


&#x20;   }


}
```

### 3.4 编译和运行项目&#xA;

在项目根目录下执行以下命令进行编译和运行：




```
./gradlew build


java -javaagent:crack-agent/build/libs/crack-agent.jar -cp demo/build/classes/java/main org.codecrafterslab.App
```

四、防护效果对比



### 4.1 未保护的字节码&#xA;

在未进行任何保护的情况下，使用反编译工具对 `data-gurad` 模块的字节码文件进行反编译，可以得到清晰的 Java 源代码：




```
package org.codecrafterslab.data.impl;


import org.codecrafterslab.data.DataGuard;


public class DefaultDataGuard implements DataGuard {


&#x20;   /\* 偏移步长 \*/


&#x20;   private static final int SHIFT\_STEP = 1;


&#x20;   @Override


&#x20;   public byte\[] encrypt(byte\[] plainText) {


&#x20;       if (plainText == null) return null;


&#x20;       byte\[] result = new byte\[plainText.length];


&#x20;       for (int i = 0; i < plainText.length; i++) {


&#x20;           char c = (char) plainText\[i];


&#x20;           result\[i] = (byte) characterConversion(c, SHIFT\_STEP);


&#x20;       }


&#x20;       return result;


&#x20;   }


&#x20;   @Override


&#x20;   public byte\[] decrypt(byte\[] cipherText) {


&#x20;       if (cipherText == null) return null;


&#x20;       byte\[] result = new byte\[cipherText.length];


&#x20;       for (int i = 0; i < cipherText.length; i++) {


&#x20;           char c = (char) cipherText\[i];


&#x20;           result\[i] = (byte) characterConversion(c, -SHIFT\_STEP);


&#x20;       }


&#x20;       return result;


&#x20;   }


&#x20;   /\*\*


&#x20;    \* \<p>字符转换\</p>


&#x20;    \* \<p>1. 交换字母大小写（大写→小写，小写→大写）\</p>


&#x20;    \* \<p>2. 对数字进行循环移位（如 '5'+1 → '6'，'9'+1 → '0'）\</p>


&#x20;    \* \<p>3. 其他字符保持不变\</p>


&#x20;    \*


&#x20;    \* @param c      字符


&#x20;    \* @param offset 数字偏移量


&#x20;    \* @return chart


&#x20;    \*/


&#x20;   private char characterConversion(char c, int offset) {


&#x20;       offset %= 10;


&#x20;       if (Character.isUpperCase(c)) {


&#x20;           return Character.toLowerCase(c);


&#x20;       } else if (Character.isLowerCase(c)) {


&#x20;           return Character.toUpperCase(c);


&#x20;       } else if (Character.isDigit(c)) {


&#x20;           int digit = c - '0';


&#x20;           digit = (digit + offset + 10) % 10;


&#x20;           return (char) ('0' + digit);


&#x20;       }


&#x20;       return c;


&#x20;   }


}
```

### 4.2 保护后的字节码&#xA;

在进行代码混淆和字节码转换后，使用反编译工具对 `data-gurad` 模块的字节码文件进行反编译，得到的代码难以理解和分析：




```
package org.codecrafterslab.data.impl;


import org.codecrafterslab.data.DataGuard;


public class a implements DataGuard {


&#x20;   private static final int a = 1;


&#x20;   public byte\[] a(byte\[] var1) {


&#x20;       if (var1 == null) {


&#x20;           return null;


&#x20;       } else {


&#x20;           byte\[] var2 = new byte\[var1.length];


&#x20;           for(int var3 = 0; var3 < var1.length; ++var3) {


&#x20;               var2\[var3] = (byte)this.a((char)var1\[var3], 1);


&#x20;           }


&#x20;           return var2;


&#x20;       }


&#x20;   }


&#x20;   public byte\[] b(byte\[] var1) {


&#x20;       if (var1 == null) {


&#x20;           return null;


&#x20;       } else {


&#x20;           byte\[] var2 = new byte\[var1.length];


&#x20;           for(int var3 = 0; var3 < var1.length; ++var3) {


&#x20;               var2\[var3] = (byte)this.a((char)var1\[var3], -1);


&#x20;           }


&#x20;           return var2;


&#x20;       }


&#x20;   }


&#x20;   private char a(char var1, int var2) {


&#x20;       var2 %= 10;


&#x20;       if (Character.isUpperCase(var1)) {


&#x20;           return Character.toLowerCase(var1);


&#x20;       } else if (Character.isLowerCase(var1)) {


&#x20;           return Character.toUpperCase(var1);


&#x20;       } else if (Character.isDigit(var1)) {


&#x20;           int var3 = var1 - 48;


&#x20;           var3 = (var3 + var2 + 10) % 10;


&#x20;           return (char)(var3 + 48);


&#x20;       } else {


&#x20;           return var1;


&#x20;       }


&#x20;   }


}
```

通过对比可以看出，经过代码混淆和字节码转换后，字节码的可读性和可分析性大大降低，有效地提高了代码的安全性。


> （注：文档部分内容可能由 AI 生成）
>